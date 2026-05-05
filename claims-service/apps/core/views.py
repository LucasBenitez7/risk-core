from django.db import connections
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        db_ok = True
        try:
            connections["default"].cursor()
        except Exception:
            db_ok = False

        return Response(
            {
                "status": "ok",
                "service": "claims-service",
                "version": "0.1.0",
                "database": "ok" if db_ok else "error",
            }
        )
