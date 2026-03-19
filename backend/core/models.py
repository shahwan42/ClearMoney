"""
Core models — Django representations of the existing Go/PostgreSQL schema.

All models use managed = False because Go owns the schema via golang-migrate.
Django is a read/write consumer, never a schema owner.

Like Laravel's Eloquent models with $table and $guarded, or Django's
standard models but with Meta.managed = False to prevent migration generation.
"""

import uuid

from django.db import models


class User(models.Model):
    """Maps to the 'users' table created by Go migration 000027."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'users'

    def __str__(self):
        return self.email


class Session(models.Model):
    """Maps to the 'sessions' table created by Go migration 000027."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    token = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'sessions'


class Category(models.Model):
    """Maps to the 'categories' table."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20)  # 'expense' or 'income'
    icon = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'categories'

    def __str__(self):
        return self.name


class Account(models.Model):
    """Maps to the 'accounts' table."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    institution_id = models.UUIDField(null=True, blank=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20)
    currency = models.CharField(max_length=3)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        managed = False
        db_table = 'accounts'

    def __str__(self):
        return self.name


class Transaction(models.Model):
    """Maps to the 'transactions' table."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    account_id = models.UUIDField()
    category_id = models.UUIDField(null=True, blank=True)
    type = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3)
    note = models.TextField(null=True, blank=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'transactions'
