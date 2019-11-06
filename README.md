# rhosp-vxflexos-deploy

Deployment tools for Dell EMC VxFlexOS support in RedHat Openstack Platform.

## Overview

This instruction provide detailed steps on how to enable VxFlexOS driver.

## Prerequisites

- Red Hat OpenStack Platform 13.
- VxFlexOS Gateway must be installed and accessible in the network.
- VxFlexOS Storage Data Client (SDC) must be installed on all OpenStack nodes.

## Steps

### Prepare Dell EMC container images

Red Hat OpenStack Platform supports remote registry and local registry for overcloud deployment. In this document, we only introduce local registry.

> in below examples, 192.168.24.1:8787 acts as a local registry.

#### Get container images

There are 2 options to get container images:

<details>
<summary>Pull container images from Red Hat Container Catalog</summary>

<br>Login to the registry.connect.redhat.com and pull container images from Red Hat Container Catalog.

```bash
$ docker login -u username -p password registry.connect.redhat.com
$ docker pull registry.connect.redhat.com/dellemc/rhosp13-cinder-volume-dellemc-vxflexos
$ docker pull registry.connect.redhat.com/dellemc/rhosp13-nova-compute-dellemc-vxflexos
```
</details>
<details>
<summary>Build container images from the Dockerfiles</summary>

<br>Build images for both cinder and nova containers from Dockerfiles.

```bash
$ docker build -f Dockerfile-cinder .
$ docker build -f Dockerfile-nova .
```
</details>

#### Push container images to the local registry

Tag and push it to the local registry.

```bash
$ docker tag <image_id> 192.168.24.1:8787/dellemc/openstack-cinder-volume-dellemc-vxflexos
$ docker push 192.168.24.1:8787/dellemc/openstack-cinder-volume-dellemc-vxflexos

$ docker tag <image_id> 192.168.24.1:8787/dellemc/openstack-nova-compute-dellemc-vxflexos
$ docker push 192.168.24.1:8787/dellemc/openstack-nova-compute-dellemc-vxflexos
```

### Prepare custom environment yaml

#### Define the custom docker registry

Create or edit `/home/stack/templates/custom-dellemc-container.yaml`.

```yaml
parameter_defaults:
  DockerCinderVolumeImage: 192.168.24.1:8787/dellemc/openstack-cinder-volume-dellemc-vxflexos
  DockerCinderBackupImage: 192.168.24.1:8787/dellemc/openstack-cinder-volume-dellemc-vxflexos
  DockerNovaComputeImage: 192.168.24.1:8787/dellemc/openstack-nova-compute-dellemc-vxflexos
  DockerInsecureRegistryAddress:
    - 192.168.24.1:8787
```

Above adds the director local registry IP `192.168.24.1:8787` to the `undercloud`.

#### Prepare environment yaml for VxFlexOS cinder backend

Create or edit `/home/stack/templates/custom-dellemc-cinder-conf.yaml`.

```yaml
parameter_defaults:  
  ControllerExtraConfig:
    cinder::config::cinder_config:
      scaleio/volume_driver:
        value: cinder.volume.drivers.dell_emc.scaleio.driver.ScaleIODriver
      scaleio/volume_backend_name:
        value: scaleio
      scaleio/san_ip:
        value: <VxFlexOS GATEWAY IP>
      scaleio/san_login:
        value: <SIO_USER>
      scaleio/san_password:
        value: <SIO_PASSWD>
      scaleio/sio_storage_pools:
        value: <Comma-separated list of protection domain:storage pool name>
    cinder_user_enabled_backends: ['scaleio']
```

For more information about custom block storage backend deployment, please refer to [Custom block storage backend deployment guide](https://access.redhat.com/documentation/en-us/red_hat_openstack_platform/13/html/custom_block_storage_back_end_deployment_guide).

For full detailed instruction of options, please refer to [VxFlexOS backend configuration](https://docs.openstack.org/cinder/latest/configuration/block-storage/drivers/dell-emc-vxflex-driver.html#configuration-options).

### Deploy configured changes

```bash
(undercloud) $ openstack overcloud deploy --templates \
  -e /home/stack/templates/overcloud_images.yaml \
  -e /home/stack/templates/custom-dellemc-container.yaml \
  -e /home/stack/templates/custom-dellemc-cinder-conf.yaml \
  -e <other templates>
```

The sequence of `-e` matters, Make sure the `/home/stack/templates/custom-dellemc-container.yaml` appears after the `/home/stack/templates/overcloud_images.yaml`, so that custom VxFlexOS containers can be used instead of the default one.

### Verify configured changes

After the deployment finishes successfully, `/etc/cinder/cinder.conf` in the Cinder container should reflect changes made above.

```ini
[DEFAULT]
...
enabled_backends=scaleio
...
[scaleio]
round_volume_capacity=True
san_ip=192.168.100.200
san_login=admin
san_password=password
san_thin_provision=True
sio_protection_domain_name=domain1
sio_storage_pool_name=pool1
sio_storage_pools=domain1:pool1
sio_unmap_volume_before_deletion=True
volume_backend_name=scaleio
volume_driver=cinder.volume.drivers.dell_emc.scaleio.driver.ScaleIODriver
...
```