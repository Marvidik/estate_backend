from django.urls import path
from .views import *

urlpatterns = [
    path('register/', register_user, name='register'),
    path('login/', login_user, name='login'),
    path('tenants/add/', add_tenant, name='add-tenant'),
    path('tenants/', view_all_tenants, name='view-all-tenants'),
    
    
    path('payment-issues/', create_payment_issue),
    path('create-payment/', create_payment,name='create_payment'),
    path('payments/', list_payments, name='list-payments'),
    path('create-expense/', create_expense, name='create-expense'),
    path('list-expenses/', list_expenses),
    path('monthly-summary/', monthly_summary),
    path("list-due-payment/",list_due_payments),
    path("export-data/",generate_financial_report)




]
