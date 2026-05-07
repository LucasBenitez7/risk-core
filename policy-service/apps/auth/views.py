import structlog
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

logger = structlog.get_logger()


class JWTVerifyView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        logger.info(
            "jwt_verified", user_id=str(request.user.id), username=request.user.username
        )
        return Response({"valid": True})
