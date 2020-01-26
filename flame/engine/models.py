from django.db import models

# Create your models here.


class Utilization(models.Model):

    cpu = models.FloatField()
    server_name = models.CharField(max_length=100)
    #ram = models.FloatField()
    #time_slice = models.FloatField()


class ServerGroups(models.Model):

    group = models.CharField(max_length=10) # can be one of H,S,N,L,I
    servers = models.TextField() # should be json like
