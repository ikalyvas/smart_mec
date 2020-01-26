import json

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
# Create your views here.

from .models import Utilization, ServerGroups
from .serializers import UtilizationSerializer


class UtilizationViewSet(ModelViewSet):
    serializer_class = UtilizationSerializer
    queryset = Utilization.objects.all()
    clusters = 5
    """
        I stands for Idle VMs (resource utilization <1%
        L stands for Light VMs (resource utilization 1-25%
        N stands for Normal VMs (resource utilization >25% - 60%
        S stands for Semi-Heavy VMs (resource utilization >60% - 90%
        H stands for Heavy VMs (resource utilization >90%)
    """

    @action(methods=["POST", ], detail=False)
    def initialize_table(self, request):

        for g in self.vm_groups:
            e = ServerGroups()
            e.group = g
            e.servers = {}
            e.save()
        return Response()

    def classify_vm_to_group(self, cpu_load, vm):

        # find in which group the vm is in if present
        # then remove it from this group
        # and add it to the new group

        vm_groups_from_db = ServerGroups.objects.select_for_update().all()
        with transaction.atomic():
            print(f"Database table after classifying is {ServerGroups.objects.all().values()}")
            groups_ = {s.group: json.loads(s.servers.replace('\'', '\"')) for s in vm_groups_from_db}
            print(f"Database table in python obj is {groups_}")
            current_group = self.find_vm(vm, groups_)
            if current_group:
                print(f'Removing {vm} from current group {current_group}')
                print(f'Existing vms in {current_group}: {list(groups_[current_group].keys())}')
                groups_[current_group].pop(vm)
                print(f'{list(groups_[current_group].keys())} left after removal of {vm}')

            if cpu_load < 1/100:
                print(f'Classifying {vm}/{cpu_load} to Idle group')
                groups_['I'][vm] = cpu_load
            if 1/100 <= cpu_load <= 25/100:
                print(f'Classifying {vm}/{cpu_load} to Light group')
                groups_['L'][vm] = cpu_load
            if 25/100 < cpu_load <= 60/100:
                print(f'Classifying {vm}/{cpu_load} to Normal group')
                groups_['N'][vm] = cpu_load
            if 60/100 < cpu_load <= 90/100:
                print(f'Classifying {vm}/{cpu_load} to Semi-Heavy group')
                groups_['S'][vm] = cpu_load
            if 90/100 < cpu_load:
                print(f'Classifying {vm}/{cpu_load} to Heavy group')
                groups_['H'][vm] = cpu_load

            ServerGroups.objects.filter(group='H').update(servers=str(groups_['H']))
            ServerGroups.objects.filter(group='S').update(servers=str(groups_['S']))
            ServerGroups.objects.filter(group='N').update(servers=str(groups_['N']))
            ServerGroups.objects.filter(group='L').update(servers=str(groups_['L']))
            ServerGroups.objects.filter(group='I').update(servers=str(groups_['I']))

            print(f"Database table after classifying is {ServerGroups.objects.all().values()}")
            return groups_

    def find_vm(self, vm, groups):
        """
        :param vm:
        :return: the group of VMs that currently exists (if exists)
        """
        for group, container in groups.items():
            if vm in container.keys():
                print(f'Found {vm} in {group}')
                return group

    def create(self, request, *args, **kwargs):
        """

        :param request:
        :param args:
        :param kwargs:
        :return: Endpoint to be triggered by the client or server in order to re-cluster the group of VMs
        """
        recluster = request.data.get('recluster')
        cpu = request.data.get('cpu')
        vm = request.data.get('server_name')
        if recluster:
            self.classify_vm_to_group(cpu, vm)

    @action(detail=False, methods=["POST", ])
    def read_initial_data(self, request):

        #{"initial_data": [{"server2": 0.01,
        #                   "server3": 0.23,
        #                   "server1": 0.45,
        #                   "server4": 0.57,
        #                   "server5": 0.91
        #                   }
        #                  ]
        #
        # }
        """
        :param request: contain cpu load per line
        :return: perform a first clustering
        """

        initial_data = request.data.get('initial_data')
        if isinstance(initial_data, str):
            try:
                with open(initial_data) as f:
                    for line in f:
                        vm, load = line.split(',')
                        groups = self.classify_vm_to_group(float(load), vm)
                    return Response(data=groups, status=status.HTTP_200_OK)
            except FileNotFoundError as e:
                return Response(data={'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        elif isinstance(initial_data, list):
            for vm, load in initial_data[0].items():
                groups = self.classify_vm_to_group(load, vm)
            return Response(data=groups, status=status.HTTP_200_OK)

    @action(detail=False)
    def calculate_task_resources(self, request):

        """
        :param t: According to the equation 1 the task resource in bytes
        :return:  t% = (t *  0.25)/2000
        """
        vm_groups_from_db = ServerGroups.objects.select_for_update().all()

        t = request.data.get('task_resource')
        task_resource = (t * 0.25)/2000

        with transaction.atomic():
            groups_ = {s.group: json.loads(s.servers.replace('\'', '\"')) for s in vm_groups_from_db}
            if task_resource < 25/100: # LT task and needs to be allocated on S or H groups
                vms = list(groups_['H'].items()) + list(groups_['S'].items())
                vms = sorted(vms, key=lambda x: x[1])
                print(f"VMs after sorting are {vms}.Task with resource requirement {task_resource} will be allocated at the VM with less utilization:{vms[0][0]}/{vms[0][1]}")
                return Response(data=vms[0][0], status=status.HTTP_200_OK)
            if 25/100 <= task_resource < 60/100:
                vms = list(groups_['N'].items()) + list(groups_['L'].items())
                vms = sorted(vms, key=lambda x: x[1])
                print(f"VMs after sorting are {vms}.Task with resource requirement {task_resource} will be allocated at the VM with less utilization:{vms[0][0]}/{vms[0][1]}")
                return Response(data=vms[0][0], status=status.HTTP_200_OK)
            if 60/100 <= task_resource: # HT
                vms = list(groups_['L'].items()) + list(groups_['I'].items())
                vms = sorted(vms, key=lambda x: x[1])
                print(f"VMs after sorting are {vms}.Task with resource requirement {task_resource} will be allocated at the VM with less utilization:{vms[0][0]}/{vms[0][1]}")
                return Response(data=vms[0][0], status=status.HTTP_200_OK)

