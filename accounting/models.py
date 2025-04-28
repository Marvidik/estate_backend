from django.db import models
from django.contrib.auth.models import User


class Estate(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Account(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    estate = models.ForeignKey(Estate, on_delete=models.CASCADE, related_name='accounts')
    is_admin = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.estate.name}"


class Tenant(models.Model):
    estate = models.ForeignKey(Estate, on_delete=models.CASCADE, related_name='tenants')
    full_name = models.CharField(max_length=255)
    house_number = models.CharField(max_length=100, blank=True)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_due = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_owing = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name} ({self.house_number})"

    def update_balance(self):
        self.is_owing = self.total_paid < self.total_due
        self.save()




class Expense(models.Model):
    estate = models.ForeignKey(Estate, on_delete=models.CASCADE, related_name='expenses')
    category = models.CharField(max_length=100, choices=[
        ('repairs', 'Repairs'),
        ('security_salary', 'Security Salary'),
        ('diesel', 'Diesel'),
        ('others', 'Others'),
    ])
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_spent = models.DateField(auto_now_add=True)
    recorded_by = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.category} - {self.amount} ({self.estate.name})"

class PaymentIssue(models.Model):
    estate = models.ForeignKey(Estate, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)  # e.g. "Security Fee - April"
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    date_issued = models.DateField(auto_now_add=True)


class TenantPaymentDue(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    issue = models.ForeignKey(PaymentIssue, on_delete=models.CASCADE, related_name='tenant_dues')
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    date_paid = models.DateField(null=True, blank=True)


class Payment(models.Model):
    estate = models.ForeignKey(Estate, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100)  # can be replaced with FK to PaymentIssue.title
    issue = models.ForeignKey(PaymentIssue, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)