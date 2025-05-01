from django.contrib import admin
from .models import Estate, Account, Tenant, Expense, PaymentIssue, TenantPaymentDue, Payment,PasswordResetOTP

# Register your models here
admin.site.register(Estate)
admin.site.register(Account)
admin.site.register(Tenant)
admin.site.register(Expense)
admin.site.register(PaymentIssue)
admin.site.register(TenantPaymentDue)
admin.site.register(Payment)
admin.site.register(PasswordResetOTP)
