# views.py
from rest_framework.decorators import authentication_classes, permission_classes, api_view
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from .models import Estate, Account,Tenant,Payment,Expense
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from .models import PaymentIssue, TenantPaymentDue,Tenant
from .serializers import PaymentIssueSerializer,PaymentSerializer,ExpenseSerializer
from django.db import transaction
from datetime import datetime
from django.db.models import Sum

import io
import pandas as pd
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from io import BytesIO
from django.http import HttpResponse



@api_view(['POST'])
def register_user(request):
    """
    Register a new user and estate in an atomic transaction.
    """
    data = request.data

    if User.objects.filter(username=data['username']).exists():
        return Response({"error": "Username already taken"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            estate = Estate.objects.create(
                name=data['estate_name'],
                address=data.get('estate_address', '')
            )

            user = User.objects.create(
                username=data['username'],
                email=data['email'],
                password=make_password(data['password'])
            )

            Account.objects.create(user=user, estate=estate, is_admin=True)

            return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def login_user(request):
    """
    Expected JSON:
    {
        "username": "admin1",
        "password": "securepass123"
    }
    """
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)

    if user:
        token, created = Token.objects.get_or_create(user=user)
        account = Account.objects.get(user=user)
        return Response({
            "token": token.key,
            "username": user.username,
            "email": user.email,
            "estate": account.estate.name,
            "estate_id": account.estate.id,
            "is_admin": account.is_admin
        })
    return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def add_tenant(request):
    user = request.user
    account = Account.objects.get(user=user)
    
    if not account.is_admin:
        return Response({"error": "Only estate admins can add tenants."}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    tenant = Tenant.objects.create(
        estate=account.estate,
        full_name=data['full_name'],
        house_number=data['house_number']
    )
    return Response({
        "message": "Tenant added successfully",
        "tenant_id": tenant.id,
        "name": tenant.full_name
    }, status=status.HTTP_201_CREATED)
    
    
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def view_all_tenants(request):
    """
    View all tenants in the same estate as the logged-in user.
    """
    user = request.user
    account = Account.objects.get(user=user)

    if not account.is_admin:
        return Response({"error": "Only estate admins can view tenants."}, status=status.HTTP_403_FORBIDDEN)

    tenants = Tenant.objects.filter(estate=account.estate)
    tenant_list = []

    for tenant in tenants:
        tenant_list.append({
            "tenant_id": tenant.id,
            "full_name": tenant.full_name,
            "house_number": tenant.house_number,
        })

    return Response({"tenants": tenant_list}, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_payment_issue(request):
    # Ensure the user has an associated estate through the Account model
    try:
        account = Account.objects.get(user=request.user)
        estate = account.estate
    except Account.DoesNotExist:
        return Response({"error": "User does not have an associated estate"}, status=status.HTTP_400_BAD_REQUEST)

    # Start the atomic transaction to ensure all operations succeed or fail together
    with transaction.atomic():
        # Create and save the Payment Issue, associating it with the estate
        serializer = PaymentIssueSerializer(data=request.data)
        if serializer.is_valid():
            issue = serializer.save(estate=estate)
            
            # Retrieve all tenants in the same estate
            tenants = Tenant.objects.filter(estate=estate)
            dues = []
            for tenant in tenants:
                dues.append(TenantPaymentDue(
                    tenant=tenant,
                    issue=issue,
                    amount_due=issue.amount
                ))
            
            # Bulk create all TenantPaymentDue records
            TenantPaymentDue.objects.bulk_create(dues)

            # Return the payment issue details in response
            return Response(PaymentIssueSerializer(issue).data, status=status.HTTP_201_CREATED)
        else:
            # If the serializer is invalid, rollback the transaction and return errors
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_payment(request):
    """
    Endpoint for the admin to create a payment record for a tenant.
    The admin specifies the tenant who made the payment and the payment details.
    """
    tenant_id = request.data.get('tenant')  # Match the serializer field name
    if not tenant_id:
        return Response({"detail": "Tenant ID is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Get the estate from the admin (logged-in user)
    try:
        account = Account.objects.get(user=request.user)
        estate = account.estate
    except Account.DoesNotExist:
        return Response({"detail": "User does not have an associated estate."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        tenant = Tenant.objects.get(id=tenant_id, estate=estate)
    except Tenant.DoesNotExist:
        return Response({"detail": "Tenant not found or does not belong to your estate."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = PaymentSerializer(data=request.data)
    if serializer.is_valid():
        try:
            with transaction.atomic():
                tenant_payment_due = TenantPaymentDue.objects.select_for_update().get(
                    id=request.data.get('payment_due_id'),
                    tenant=tenant
                )

                if tenant_payment_due.is_paid:
                    return Response({"detail": "Payment already made for this issue."}, status=status.HTTP_400_BAD_REQUEST)

                payment = serializer.save(tenant=tenant, estate=tenant.estate)

                tenant_payment_due.is_paid = True
                tenant_payment_due.date_paid = payment.date
                tenant_payment_due.save()

                tenant.update_balance()

                return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

        except TenantPaymentDue.DoesNotExist:
            return Response({"detail": "Payment due not found."}, status=status.HTTP_400_BAD_REQUEST)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_payments(request):
    try:
        account = Account.objects.get(user=request.user)
    except Account.DoesNotExist:
        return Response({"detail": "Account not found for the user."}, status=status.HTTP_400_BAD_REQUEST)

    # Fetch only payments for the user's estate
    payments = Payment.objects.filter(estate=account.estate).order_by('-date')
    serializer = PaymentSerializer(payments, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_expense(request):
    try:
        account = Account.objects.get(user=request.user)
    except Account.DoesNotExist:
        return Response({"detail": "Account not found for the user."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ExpenseSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(recorded_by=account, estate=account.estate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_expenses(request):
    try:
        account = Account.objects.get(user=request.user)
        estate = account.estate
    except Account.DoesNotExist:
        return Response({"detail": "User does not have an associated estate."}, status=status.HTTP_400_BAD_REQUEST)

    expenses = Expense.objects.filter(estate=estate).order_by('-date_spent')
    serializer = ExpenseSerializer(expenses, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def monthly_summary(request):
    try:
        account = Account.objects.get(user=request.user)
        estate = account.estate
    except Account.DoesNotExist:
        return Response({"detail": "User does not have an associated estate."}, status=status.HTTP_400_BAD_REQUEST)

    # Get month and year from query params or use current month/year
    month = request.query_params.get('month')
    year = request.query_params.get('year')

    try:
        month = int(month) if month else datetime.now().month
        year = int(year) if year else datetime.now().year
    except ValueError:
        return Response({"detail": "Month and year must be integers."}, status=status.HTTP_400_BAD_REQUEST)

    if month < 1 or month > 12:
        return Response({"detail": "Invalid month. Must be between 1 and 12."}, status=status.HTTP_400_BAD_REQUEST)

    # Sum of expenses for the selected month
    total_expenses = Expense.objects.filter(
        estate=estate,
        date_spent__year=year,
        date_spent__month=month
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Sum of payments for the selected month
    total_payments = Payment.objects.filter(
        estate=estate,
        date__year=year,
        date__month=month
    ).aggregate(total=Sum('amount'))['total'] or 0

    return Response({
        "month": datetime(year, month, 1).strftime("%B"),
        "year": year,
        "total_expenses": total_expenses,
        "total_payments": total_payments
    })
    

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_due_payments(request):
    try:
        account = Account.objects.get(user=request.user)
        estate = account.estate
    except Account.DoesNotExist:
        return Response({"detail": "User does not have an associated estate."}, status=status.HTTP_400_BAD_REQUEST)

    dues = TenantPaymentDue.objects.filter(is_paid=False, tenant__estate=estate)

    data = []
    for due in dues:
        data.append({
            "tenant_id": due.tenant.id,
            "tenant_name": due.tenant.full_name,  # assuming this exists
            "amount_due": due.amount_due,
        })

    return Response(data, status=status.HTTP_200_OK)



@api_view(['GET'])
def generate_financial_report(request):
    current_date = datetime.now()

    # Get the month and year from query parameters or default to current month/year
    month = request.query_params.get('month', current_date.month)
    year = request.query_params.get('year', current_date.year)

    month = int(month)
    year = int(year)

    # Get all expenses and payments for the selected month and year
    expenses = Expense.objects.filter(date_spent__month=month, date_spent__year=year)
    payments = Payment.objects.filter(date__month=month, date__year=year)

    # Check if any data was fetched
    if not expenses or not payments:
        return HttpResponse("No data found for the given month/year.", status=404)

    # Create a Pandas DataFrame for the expenses and payments
    expense_data = []
    for expense in expenses:
        expense_data.append({
            'category': expense.category,
            'amount': expense.amount,
            'date_spent': expense.date_spent,
            'description': expense.description,
        })

    payment_data = []
    for payment in payments:
        payment_data.append({
            'tenant_name': payment.tenant.full_name,
            'amount': payment.amount,
            'date': payment.date,
            'category': payment.category,
        })

    expense_df = pd.DataFrame(expense_data)
    payment_df = pd.DataFrame(payment_data)

    # Create a financial summary report
    total_expenses = expense_df['amount'].sum()
    total_payments = payment_df['amount'].sum()

    # Create the Excel report
    wb = BytesIO()
    with pd.ExcelWriter(wb, engine='xlsxwriter') as writer:
        expense_df.to_excel(writer, sheet_name='Expenses')
        payment_df.to_excel(writer, sheet_name='Payments')

        # Add summary
        summary_data = {
            'Total Expenses': total_expenses,
            'Total Payments': total_payments,
            'Net Balance': total_payments - total_expenses,
        }
        summary_df = pd.DataFrame(list(summary_data.items()), columns=['Category', 'Amount'])
        summary_df.to_excel(writer, sheet_name='Summary')

        # Access the xlsxwriter workbook and worksheet
        workbook = writer.book
        expenses_sheet = workbook.get_worksheet_by_name('Expenses')

        # Create a pie chart for expenses category
        expense_categories = expense_df['category'].value_counts()
        chart_expenses = workbook.add_chart({'type': 'pie'})
        chart_expenses.add_series({
            'name': 'Expense Categories',
            'categories': f"=Expenses!$A$2:$A${len(expense_categories) + 1}",
            'values': f"=Expenses!$B$2:$B${len(expense_categories) + 1}",
        })
        expenses_sheet.insert_chart('E2', chart_expenses)

        # Create a bar chart for payments and expenses comparison
        chart_comparison = workbook.add_chart({'type': 'column'})
        chart_comparison.add_series({
            'name': 'Expenses',
            'categories': f"=Summary!$A$2:$A$3",
            'values': f"=Summary!$B$2:$B$3",
        })
        chart_comparison.add_series({
            'name': 'Payments',
            'categories': f"=Summary!$A$2:$A$3",
            'values': f"=Summary!$B$2:$B$3",
        })
        summary_sheet = workbook.get_worksheet_by_name('Summary')
        summary_sheet.insert_chart('D2', chart_comparison)

    wb.seek(0)  # Reset pointer to the start of the file

    # Prepare the response
    response = HttpResponse(wb, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=financial_report_{year}_{month}.xlsx'

    return response