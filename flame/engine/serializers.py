from rest_framework.serializers import ModelSerializer
from .models import Utilization


class UtilizationSerializer(ModelSerializer):

    class Meta:
        fields = "__all__"
        model = Utilization