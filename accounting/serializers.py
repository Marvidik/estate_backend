# payments/serializers.py
from rest_framework import serializers
from .models import PaymentIssue, TenantPaymentDue, Payment,Expense
from .models import Tenant  # assuming this is where your Tenant model lives

class PaymentIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentIssue
        fields = ['id', 'estate', 'title', 'amount', 'description', 'date_issued']
        read_only_fields = ['id', 'estate', 'date_issued']

class TenantPaymentDueSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)

    class Meta:
        model = TenantPaymentDue
        fields = ['id', 'tenant', 'tenant_name', 'issue', 'amount_due', 'is_paid', 'date_paid']
        read_only_fields = ['id', 'amount_due', 'is_paid', 'date_paid']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'estate', 'tenant', 'amount', 'category', 'issue', 'description', 'date', 'created_at']
        read_only_fields = ['id', 'estate', 'created_at']


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = '__all__'
        read_only_fields = ['recorded_by', 'estate', 'date_spent']