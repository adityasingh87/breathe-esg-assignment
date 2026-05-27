from core.models import Tenant

class TenantMiddleware:
    """
    Middleware that assigns the first tenant to the request for the prototype.
    In a real application, this would derive the tenant from the JWT token or subdomain.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Unconditionally assign for the prototype since DRF JWT auth happens after middleware
        request.tenant = Tenant.objects.first()
        response = self.get_response(request)
        return response
