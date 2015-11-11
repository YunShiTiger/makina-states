Makina-States based docker Images
=====================================
Idea
-----
Docker images are just :ref:`mc_project <project_creation>` based application wrapped into a docker container.
Those images are remote_less and should not rely on a full system running, we are in a docker.

Run time
++++++++++
The app is launched an managed via a ``bin/launch.sh`` (`Example <https://github.com/makinacorpus/corpus-dockerregistry/blob/master/bin/launch.sh>`_) script, which should ideally:

      - Replace the default pillar by the **configuration/pillar.sls** if it
        existsa. This is the only thing we need to do before launching a salt
        module script that does the rest.
      - Execute a salt **mc_launcher.py** (`Example <https://github.com/makinacorpus/corpus-dockerregistry/blob/master/.salt/_modules/mc_launcher.py>`_) module which runs our app after maybe
        having reconfigured it.

          - allow inbound ssh connections for allowed keys
          - reconfigure (ideally by exec'ing a subset of the sls in **.salt**)
            the container to serve the app (eg: update domain to server,
            ip of the database, registration to autodiscovery service)
          - spawn a circus daemon at the end of the configuration.
          - The module should have at least implements this interface:

            .. code-block:: python

                def sshconfig(name=PROJECT):
                    '''code to allow ssh_keys to connect'''
                    pass
                def reconfigure(name=PROJECT):
                    '''code to reconfigure the app to serve requests
                      in this specific context'''
                    pass
                def launch(name=PROJECT, ssh_config=False, re_configure=False):
                    if ssh_config:
                        ssh_config(name=name)
                    if re_configure
                        re_configure(name=name)
                    # code to launch the app in foreground

- Indeed, the app is lightly reconfigured via salt and may be given an
  overriden pillar file via a filesystem volume to help to reconfigure it.
- Volumes and files that need to be prepolulated should be filled by the
  launcher if and only if it is not already data placed into them.
- A Control-C or quit signal must inhibit any launched process more or less
  gracefully

Build time
++++++++++++++++
- We configure the image through a regular :ref:`mc_project <project_creation>` based
  saltstack project.
- All the processes inside the container must be managed if possible via circus
- POSIX Acls are now to be avoided at all cost to avoid export/import problems as tar
  is used to exchange images, the extended attributes are lost in the middle


layout inside the Image
-------------------------
This is of course an example but it reflects what we need to respect::

    /srv/salt/custom.sls      <- custom pillar
    /srv/projects/<project>
       |
       |- project/ <- application code
       |     |- Dockerfile    <- Each app needs to have a basic Dockerfile
       |     |- bin/launch.sh <- launcher that:
       |     |                   - copy $data/configuration/pillar.sls -> $pillar/init.sls
       |     |                   - reconfigure (via salt) the app
       |     |                   - launch the app in foreground
       |     |- .salt         <- deployment and reconfigure code (mc_project based)
       |     |- .salt/100_dirs_and_prerequisites.sls
       |     |- .salt/200_reconfigure.sls
       |     |- .salt/300_nginx.sls
       |     |- .salt/400_circus.sls
       |     |- .salt/_modules/mc_launcher.py
       |                code that is used to reconfigure the image
       |                at launch time (via launch.sh)
       |
       |- pillar/  <- salt extra pillar that overrides PILLAR.sample (itself
       |              overriden by data/configuration/pillar.sls)
       |
       |- data/                  <- exposed through a docker volume
             |- data/            <- persistent data root
             |- configuration/   <- deploy time pillar that is used at reconfigure
                                     time (startup of a pre-built image)

We separate the project codebase from any persistent data that is needed to be created along any container.<br/>

For this we use two root separates folders:
 - one for the clone of the codebase: **${PROJECT}**
 - and one for the persistent data: **${DATA}**

By convention, the name of the persistant data holding directory is the name of the clone folder suffixed by ``_data``.<br/>
Eg if you clone your project inside ``~/project``, the data folder will be ``~/project_data``.<br/>
The data folder can't and must not be inside the project folder as we drastically play with
unix permissions to enforce proper security and the two of those folders do not have at all the same policies.<br/>
The special folder **project_data/volume** is mounted as a docker voume inside the container at the project data directory location. We refer it as **${VOLUME}**.

You need to add a volume that will contains those subdirs:

    ${PROJECT}/
        git clone of this repository, the project code inside the
        container. this folder contains a '.salt' folder which
        describe how to install & configure this project.
        (/srv/projects/<name>/project)
    ${PROJECT}/Dockerfile
        Dockerfile to build your app
    ${PROJECT}/.salt
        mc_project configuration to configure your app
    ${DATA}/volume/
        mounted as the persistent data folder inside the container
        (/srv/projects/<name>/data), Alias ${VOLUME}
    ${DATA}/volume/configuration
        directory holding configuration bits for the running container
        that need to be edited or accessible from the host & the user
    ${DATA}/volume/data
        persistent data

Inside of the data volume, we also differentiate in term of permissions
the configuration from the datas (later is more laxist).
For the configuration directories, after the image has been launched, you ll
certainly need to gain root privileges to re-edit any files in those subdirs.

Project_data in details:

    ${VOLUME}/ssh/\*.pub
        ssh public keys to allow to connect as root
    ${VOLUME}/configuration
        contains the configuration
    ${VOLUME}/configuration/pillar.sls
        configuration file (saltstack pillar) for the container
    ${VOLUME}/data/
        top data dir

Initialise your [dev/prod] environment
----------------------------------------
Download and initialize the layout
+++++++++++++++++++++++++++++++++++

.. code-block:: bash

    export REPO_URL="http://git/orga/repo.git"
    export PROJECT="${WORKSPACE}/myproject" # where you want to put the code
    export DATA="${PROJECT}_data"           # where you want to put the data
    export VOLUME="${DATA}/volume"          # where you want to put the docker volume
    mkdir -p "${DATA}" "${VOLUME}"
    git clone "${REPO_URL}" "${PROJECT}"

OPTIONNAL: Generate a a certificate with a custom authority for testing purposes
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. code-block:: bash

    cd "${DATA}"
    DOMAIN="registryh.docker.tld"
    mkdir -p ca
    openssl genrsa -des3 -out ca/sca-key.pem
    openssl genrsa -des3 -out ca/s${DOMAIN}-key.pem
    openssl rsa -in ca/sca-key.pem -out ca/ca-key.pem
    openssl rsa -in ca/s${DOMAIN}-key.pem -out ca/${DOMAIN}-key.pem
    openssl req -new -x509 -days $((365*30)) -key ca/ca-key.pem -out ca/ca.pem\
      -subj "/C=FR/ST=dockerca/L=dockerca/O=dockerca/CN=dockerca/"
    openssl req -new -key ca/${DOMAIN}-key.pem -out ca/${DOMAIN}.csr\
      -subj "/C=FR/ST=dockerca/L=dockerca/O=dockerca/CN=*.${DOMAIN}/"
    openssl x509 -CAcreateserial -req -days $((365*30)) -in ca/${DOMAIN}.csr\
      -CA ca/ca.pem -CAkey ca-key.pem -out ca/${DOMAIN}.crt
    cat ca/${DOMAIN}.crt ca.pem > ca/${DOMAIN}.bundle.crt

Register the certificate to the host openssl configuration
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
.. code-block:: bash

    cat | sudo sh << EOF
    cp "${DATA}/ca/${domain}.bundle.crt /usr/local/share/ca-certificates\
    && update-ca-certificates
    EOF

Configure the image via the salt PILLAR
+++++++++++++++++++++++++++++++++++++++++++
You need then to fill the pillar to reconfigure your container at running time.
  - setup a domain to serve for the registry (the virtualhost name)
  - (opt) the SSL certificate informations

.. code-block:: bash

    mkdir -p "${VOLUME}/configuration"
    cp .salt/PILLAR.sample "${VOLUME}/configuration/pillar.sls"
    sed -re "s/makina-projects.projectname/makina-projects.registry/g"\
      -i "${VOLUME}/configuration/pillar.sls"
    $EDITOR "${VOLUME}/configuration/pillar.sls" # Adapt to your needs

Build & Run
---------------
**Be sure to have completed the initial configuration (SSL, PILLAR) before launching the container.**
You may not need to **build** the image, you can directly download it from the docker-hub.

.. code-block:: bash

    docker pull <orga>/<image>
    # or docker build -t <orga>/<image> .

Run

.. code-block:: bash

    docker run -ti\
      -v "${DATA}/volume":/srv/projects/registry/data <orga>/<image>

DNS configuration
++++++++++++++++++
When your container is running and you want to access it locally, in development mode,<br/>
just inspect and register it in your /etc/hosts file can avoid you tedious setup

Assuming that you configured the container to respond to **${DOMAIN}**.

.. code-block:: bash

    IP=$(sudo docker inspect -f '{{ .NetworkSettings.IPAddress }}' <YOUR_CONTAINER_ID>)
    cat | sudo sh << EOF
    sed -i -re "/${DOMAIN}/d" /etc/hosts
    echo $IP ${DOMAIN}>>/etc/hosts
    EOF

Get further in the development of an image
++++++++++++++++++++++++++++++++++++++++++++++
- [doc/Hack.md](doc/Hack.md)
- [doc/Registry.md](doc/Registry.md)


