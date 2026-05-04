class BaseAction:
    """Base class for all action handlers"""
    
    def __init__(self, user):
        self.user = user
    
    def format_success(self, message, data=None):
        """Format successful response"""
        return {
            "success": True,
            "message": message,
            "data": data
        }
    
    def format_error(self, error):
        """Format error response"""
        return {
            "success": False,
            "error": error
        }
    
    def format_access_denied(self, permission):
            """Format access denied response"""
            role_display = self.user.role if hasattr(self.user, 'role') else 'Unknown'
            return {
                "success": False,
                "message": f"❌ Access Denied: You don't have permission to perform this action.\n\n"
                        f"Required permission: {permission}\n"
                        f"Your role: {role_display}\n\n"
                        f"Please contact your administrator if you need this access.",
                "access_denied": True
            }