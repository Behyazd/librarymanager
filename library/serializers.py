# library/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Book, Member, Loan, Notification


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')


class BookSerializer(serializers.ModelSerializer):
    available_copies = serializers.IntegerField(read_only=True)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = Book
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'qr_code')


class MemberSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    active_loans_count = serializers.IntegerField(read_only=True)
    can_borrow = serializers.BooleanField(read_only=True)

    class Meta:
        model = Member
        fields = '__all__'
        read_only_fields = ('member_code', 'created_at')


class LoanSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book.title', read_only=True)
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = Loan
        fields = '__all__'
        read_only_fields = ('created_at',)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ('created_at',)


# Serializer برای ثبت‌نام کاربر
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ('username', 'password', 'email', 'first_name', 'last_name')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=validated_data.get('email', ''),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user