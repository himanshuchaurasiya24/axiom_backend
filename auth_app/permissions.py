from rest_framework import permissions
class IsUserNotLocked(permissions.BasePermission):
    """
    Custom permission to only allow access to the users if theit account is not locked.
    """
    message = "Your account is locked please contact support."
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated :
            return False
        return not request.user.is_locked
