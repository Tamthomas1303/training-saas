from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User

DEFAULT_PASSWORD = 'Anhminh@12345'


class UserAdminSerializer(serializers.ModelSerializer):
    """Serializer cho man Nguoi dung (Admin quan tri). Port UserService.gs::upsertUser -
    mat khau mac dinh khi tao moi khong truyen password, ghi de bang set_password (hash)."""

    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True, default='')
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'password', 'full_name', 'role', 'job_title', 'restaurant',
            'restaurant_name', 'trainer_zone', 'google_email', 'status',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from restaurants.models import Restaurant

            self.fields['restaurant'].queryset = Restaurant.objects.filter(tenant=request.user.tenant)

    def create(self, validated_data):
        password = validated_data.pop('password', '') or DEFAULT_PASSWORD
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', '')
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True, default='')

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'full_name',
            'role',
            'job_title',
            'trainer_zone',
            'status',
            'avatar_url',
            'tenant',
            'tenant_name',
            'restaurant',
            'restaurant_name',
        ]
        read_only_fields = fields


class TenantAwareTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['tenant_id'] = user.tenant_id
        token['role'] = user.role
        token['full_name'] = user.full_name
        token['restaurant_id'] = user.restaurant_id
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data
