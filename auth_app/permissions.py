from rest_framework import permissions

class IsUserNotLocked(permissions.BasePermission):
    """
    Custom permission to only allow access to the users if their account is not locked.
    """
    message = "Your account is locked please contact support."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return not request.user.is_locked

class IsSubscriptionActive(permissions.BasePermission):
    """
    Custom permission to block access if subscription has expired.
    """
    message = "Your plan has expired. To use, you need to upgrade your account."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Admins bypass subscription checks
        if request.user.is_staff or request.user.is_superuser:
            return True
            
        return request.user.is_subscription_active

class IsSelfOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow the user to retrieve/modify their own object.
    Admins (is_staff or is_superuser) are granted full access.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True            
        return obj == request.user