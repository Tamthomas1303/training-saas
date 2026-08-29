from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import (
    BrandSettings,
    EmailSettings,
    GradingConfig,
    GradingConfigHistory,
    RoleMenuConfigHistory,
    User,
)

DEFAULT_PASSWORD = 'Anhminh@12345'


class UserAdminSerializer(serializers.ModelSerializer):
    """Serializer cho man Nguoi dung (Admin quan tri). Port UserService.gs::upsertUser -
    mat khau mac dinh khi tao moi khong truyen password, ghi de bang set_password (hash)."""

    restaurant_name = serializers.SerializerMethodField()
    # Prompt_Fix_DotA_29.08.md muc 6 (#17b/#17c) - man Nguoi dung them cot Nha hang/Phong ban +
    # Vi tri lam viec, lay tu ho so nhan su LIEN KET (Employee.user, tao qua onboarding tu dong/
    # import) khi tai khoan (User) khong tu co san restaurant rieng (vd tai khoan trainer/admin
    # dung chung, khong gan 1 nha hang co dinh).
    position = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # Prompt_Fix_DotA_29.08.md muc 1 - override tuong minh de TU TAY kiem tra trung (xem
    # validate_username), thay vi de UniqueValidator tu dong cua DRF bao loi tieng Anh chung
    # chung ("user with this username already exists."). username van sua duoc binh thuong qua
    # PATCH (khong nam trong read_only_fields).
    username = serializers.CharField(max_length=150)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'password', 'full_name', 'role', 'job_title', 'restaurant',
            'restaurant_name', 'position', 'trainer_zone', 'google_email', 'status',
            'must_change_password', 'archived_at',
        ]
        # must_change_password/archived_at CHI doi qua action rieng (reset-password/archive/
        # restore ben duoi) - khong cho sua truc tiep qua form Sua thong tin thuong, tranh Admin
        # vo tinh bat/tat co nay khi chi dinh sua ten/vai tro.
        read_only_fields = ['must_change_password', 'archived_at']

    def get_restaurant_name(self, obj):
        if obj.restaurant_id:
            return obj.restaurant.name
        employee = getattr(obj, 'employee', None)
        if employee and employee.restaurant_id:
            return employee.restaurant.name
        return ''

    def get_position(self, obj):
        employee = getattr(obj, 'employee', None)
        return employee.position if employee else ''

    def validate_username(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Tên đăng nhập không được để trống.')
        qs = User.objects.filter(username=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Tên đăng nhập đã được sử dụng, vui lòng chọn tên khác.')
        return value

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
            'must_change_password',
        ]
        read_only_fields = fields


class BrandSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrandSettings
        fields = ['system_name', 'logo_url', 'favicon_url', 'brand_hex', 'theme_mode']


class GradingConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradingConfig
        fields = [
            'exam_pass_percent', 'skill_pass_percent', 'weight_exam', 'weight_practice',
            'weight_theory', 'weight_practical', 'days_staff', 'days_supervisor_deputy',
            'days_manager_chef', 'probation_pass_rule', 'allowance_per_person',
            'allowance_exam_min', 'allowance_skill_min', 'allowance_scope',
            'cert_positions_required', 'cert_program_rule', 'updated_at',
        ]
        read_only_fields = ['updated_at']


class GradingConfigHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.full_name', read_only=True, default='')

    class Meta:
        model = GradingConfigHistory
        fields = ['id', 'changed_at', 'changed_by_name', 'field', 'old_value', 'new_value']


class RoleMenuConfigHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.full_name', read_only=True, default='')

    class Meta:
        model = RoleMenuConfigHistory
        fields = ['id', 'changed_at', 'changed_by_name', 'role', 'old_keys', 'new_keys']


class EmailSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailSettings
        fields = [
            'from_display_name', 'recipients', 'cc', 'weekly_enabled', 'weekly_weekday',
            'weekly_hour', 'monthly_enabled', 'monthly_day', 'monthly_hour', 'timezone',
        ]


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
