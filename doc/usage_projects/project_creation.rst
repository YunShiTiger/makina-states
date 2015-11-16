Project management
=====================

.. contents::

.. _project_creation:

Intro
--------------------------------
This page is the most important thing you ll have to read about makina-states as a **developer consumer**, take the time it needs and deserves.

Never be afraid to go read makina-states code, it will show you how to configure
and extend it. It is simple python and yaml.

See python exemples:

    - `the modules <https://github.com/makinacorpus/makina-states/tree/master/mc_states/modules>`_ (`saltstack doc about modules <https://docs.saltstack.com/en/latest/ref/modules/>`_)
    - `the states <https://github.com/makinacorpus/makina-states/tree/master/mc_states/states>`_ (`saltstack doc about states <https://docs.saltstack.com/en/latest/ref/states/>`_)
    - `the runners <https://github.com/makinacorpus/makina-states/tree/master/mc_states/runners>`_ (`saltstack doc about runners <https://docs.saltstack.com/en/latest/ref/runners/>`_)

See formulaes exemples:
    - `saltstack doc about states formulaes <https://docs.saltstack.com/en/latest/ref/states/>`_
    - `saltstack doc about states formulaes2 <https://docs.saltstack.com/en/latest/topics/tutorials/states_pt1.html>`_
    - `the localsettings <https://github.com/makinacorpus/makina-states/tree/master/localsettings>`_
    - `the services <https://github.com/makinacorpus/makina-states/tree/master/services>`_

Specifications
------------------
See the original :ref:`specification <project_corpus>`, and specially the :ref:`layout <project_spec_layout>`, the :ref:`install <project_spec_proc_install>` procedure, and the :ref:`fixperms<project_spec_proc_fixperms>` procedure.

A good sumup of the spec is as follow, but please read it once...

    - There is a separate repo distributed along the project named **pillar** to
      store configuration variables, passwords and so on.
    - Projects are deployed via instructions based on saltstack which are
      contained into the **.salt** folder inside the codebase.

The deployment includes global phases in this order:

    - archive ``archive.sls``
    - sync code from remotes if there are remotes
    - sync/install custom salt modules (exec, states, etc) from the codebase if any
    - fixperms (``fixperms.sls``)
    - install  (``install.sls``)
    - fixperms
    - rollback (``rollback.sls``)if error

Some of those phases can be edited via the user, and some other not (install, & sync steps).

That will explain that in your **.salt** folder, you have at least ``install.sls``,
``fixperms.sls``, ``rollback.sls``, and for old projects ``notify.sls``.

All other sls found at **toplevel** which are not those ones are executed in
lexicographical order (alphanum) and the convention is to name them ``\d\d\d_NAME.sls``

The ``PILLAR.sample`` file contains default configuration variable for your
project and helps you to know what variable to override in your custom pillar.

Initialization
++++++++++++++++
- a project in corpus / makina-states is a git repository checkout which contains the code
  and a well known saltstack based procedure to deploy it
  from end to end in the **.salt** folder.
- By default the project procedure is done via a `masterless salt call <http://docs.saltstack.com/en/latest/topics/tutorials/quickstart.html>`_.
- The first thing to do is to create a **nest** from such a project, **IF IT IS NOT ALREADY DONE** (just ls /srv/projects to check):

  .. code-block:: bash

    salt-call --local mc_project.deploy <project_name> # dont be long, dont use - & _

- This empty structure respects the aforementioned corpus reactor anatomy, and is just an useless helloword project which should look like::

    /srv/projects/<project_name>
        |
        |- pillar/init.sls: override values in PILLAR.sample and define
        |                   any other arbitrary pillar DATA.
        |
        |- data/: anything which is persisted to disk must live here
        |         from drupal sites/default/files, python eggs, buildouts parts,
        |         gems cache, sqlite files, static files, docroots, etc.
        |
        |- project/ <- a checkout or your project
        |   |-  .git
        |   |-  codebase
        |   |-  .salt
        |     |- _modules : custom salt python exec modules
        |     |- _states  : custom salt python states modules
        |     |- _runners : custom salt python runners modules
        |     |- _sdb     : custom salt python sdb modules
        |     |- _...
        |     |
        |     |- PILLAR.sample
        |     |- task_foo.sls
        |     |- 00_deploy.sls
        |
        [ If "remote_less" is False (default)
        |- git/project.git: bare git repos synchronnized (bi-directional)
        |                   with project/ used by git push style deployment
        |- git/pillar.git:  bare git repos synchronnized (bi-directional)
                            with pillar/ used by git push style deployment


- What you want to do is to replace the ``project`` folder by your repo.
  This one contains your code, as asual, plus the **.salt** folder,
- **WELL Understand** what is :

    - a `salt SLS <http://docs.saltstack.com/en/latest/topics/tutorials/starting_states.html#moving-beyond-a-single-sls>`_ , it is the nerve of the war.
    - the `Pillar of salt <http://docs.saltstack.com/en/latest/topics/tutorials/pillar.html>`_.

- **be ware**, on the production server the ``.git/config`` is linked with the
  makina-states machinery and you cannot replace it blindly, you must use :ref:`git foo` to
  do it.
- Ensure to to have at least in your project git folder:

    - ``.salt/PILLAR.sample``: configuration default values to use in SLSes
    - ``.salt/archive.sls``: archive step
    - ``.salt/fixperms.sls``: fixperm step
    - ``.salt/rollback.sls``: rollback step

- You can then add as many SLSes as you want, and the ones directly in **.salt** will be executed in alphabetical order except the ones beginning with **task_** (task_foo.sls). Indeed the ones beginning with **task_** are different beasts and are intended to be either included by your other slses to factor code out or to be executed manually via the ``mc_project.run_task`` command.
- You can and must have a look for inspiration on :ref:`projects_project_list`

Deploying, two ways of doing things
------------------------------------
To build and deploy your project we provide two styles of doing style that should be appropriate for most use cases.

The common workflow is:

    - use ``mc_project.init_project`` to create the structure to host your project
    - use ``mc_project.report`` to verify things are in place
    - git push/or edit then push the pillar ``/srv/projects/<project>/pillar`` to configure the project
    - git push/or edit then push the code inside ``/srv/projects/<project>/project``
    - launch the deploy
    - Wash, Rince, Repeat

mc_project.init_project: initialize the layout
++++++++++++++++++++++++++++++++++++++++++++++++
The following command is the nerve of the war::

    salt-call \
        --local -lall \
        mc_project.init_project $project [remote_less=false/true]

- ``--local -lall`` instructs to run in masterless mode and extra verbosity
- ``mc_project.init_project $project`` instructs to create the layout of the name ``$project`` project living into ``/srv/projects/$project/project``
- (opt) ``remote_less`` instructs to deploy with or without the git repos that allow users to use a **git push to prod to deploy** workflow.

    - If ``remote_less=true``, the git repos wont be created, and you wont be
      able to push to git remotes to deploy your project (you ll have to do it
      directly on the server, by the :ref:`hand procedure <project_hand_procedure>`.

mc_project.deploy, the main entry point
+++++++++++++++++++++++++++++++++++++++++
The following command is the nerve of the war::

    salt-call \
        --local -lall \
        mc_project.deploy $project\
         [only=step2[,step1]] \
         [only_steps=step2[,step1]]

- ``--local -lall`` instructs to run in masterless mode and extra verbosity
- ``mc_project.deploy $project`` instructs to deploy the name ``$project`` project living into ``/srv/projects/$project/project``
- (opt) ``only`` instructs to execute only the named global phases, and when deploying directly onto a machine, you will certainly have to use ``only=install,fixperms,sync_modules``
  to avoid the archive/sync/rollback steps.
- (opt) ``only_steps`` instruct to execute only a specific or multiple specific sls from the **.salt** folder during the **install** phase.


.. _project_hand_procedure:

Directly on the remote server, by hand
+++++++++++++++++++++++++++++++++++++++
Either directly from the deployment host as root:

Initialise the layout (only the first time)

.. code-block:: bash

    ssh root@remoteserver
    export project="foo"
    salt-call --local -ldebug mc_project.init_project $project


Edit the pillar

.. code-block:: bash

    ssh root@remoteserver
    export project="foo"
    cd /srv/projects/$project
    # maybe you want to edit before pillar deploy
    $ÊDITOR pillar/init.sls
    cd pillar;git commit -m foo;git push;cd ..

Update the project code base from git

.. code-block:: bash

    ssh root@remoteserver
    export project="foo"
    cd /srv/projects/$project/project
    # if not already done, add your project repo remote
    git remote add g https://github.com/o/myproject.git
    # in any cases, update your code
    git fetch --all
    git reset --hard remotes/g/<the branch to deploy>
    git push --force origin HEAD:master

Launch deploy

.. code-block:: bash

    ssh root@remoteserver
    # launch the deployment
    export project="foo"
    salt-call --local -ldebug \
        mc_project.deploy $project \
        only=install,fixperms,sync_modules
    # or to deploy only a specific sls
    salt-call --local -ldebug \
        mc_project.deploy $project \
        only=install,fixperms,sync_modules only_steps=000_foo.sls
    git push o HEAD:<master> # replace master by the branch you want to push
                             # back onto your forge

VARIANT: Deploy by hand, on a vagrant VM
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In development, our best practises are not to pull from our private git repositories
directly from inside the VM.

The HOST on which the virtualbox is running, is on the contrary controlled
by the developer and it's more safe to pull/push the code from here.

To sum up, any **git push/pull** operation has to be done **from the localhost**
and not the vm.

In other words, the HOST can access any of the VM files with the help of a shared **sshfs** mountpoint ``./VM``.
And the HOST can also access the outside repositories.
So the host in the interface that will push code inside the VM.

This setup involves using the ``remote_less`` feature of ``mc_project`` where
we do not deploy via a ``git push`` nor use ``archive/rollback`` mechanims.

Initialise/launch a `makina-states/vms <https://github.com/makinacorpus/vms>`_ box (this will take some time, specially
the first time)

.. code-block:: bash

    git clone https://github.com/makinacorpus/vms
    cd vms
    ./manage.sh init

Open one console connected to the VM as **root**

.. code-block:: bash

    ./manage.sh ssh
    sudo su # (default password: vagrant)

Initialise the layout (only the first time)

.. code-block:: bash

    ssh root@remoteserver
    export project="foo"
    salt-call --local -ldebug mc_project.init_project $project remote_less=true

Edit the pillar

.. code-block:: bash

    cd /srv/projects/$project/pillar
    $EDITOR init.sls
    git commit -am up

Open a second shell, on your local machine ( **not on the VM** )
where you ll update the project code base from git.

.. code-block:: bash

    export project="foo"
    cd vms/VM/srv/projects/$project/project
    # if not already done, add your project repo remote
    git remote add o https://github.com/o/myproject.git
    # in any cases, update your code
    git fetch --all
    git reset --hard remotes/o/<the branch to deploy>

On the former shell ssh-connected to the vagrant box, launch deploy

.. code-block:: bash

    salt-call --local -ldebug mc_project.deploy $project only=install,fixperms,sync_modules
    # or to deploy only a specific sls
    salt-call --local -ldebug \
        mc_project.deploy $project \
        only=install,fixperms,sync_modules only_steps=000_foo.sls

When you want to commit your changes, return to the second shell, on your local
machine

.. code-block:: bash

    export project="foo"
    cd vms/VM/srv/$project/project
    git push o HEAD:<master> # replace master by the branch you want to push
                             # back onto your forge

.. _git foo:

Deploy with git instructions
++++++++++++++++++++++++++++++
Reminder
~~~~~~~~~~~
- **WARNING**: you can use it only if you provisionned your project with
  attached remotes (the default)
- Remember use the remotes inside ``/srv/projects/<project>/git`` and not directly the
  working copies
- If you push on the pillar, it does not trigger a deploy
- If you push on the project,  it triggers the full deploy procedure
  including archive/sync/rollback.
- To get useful push informations, on the remote server to deploy to, just do

.. code-block:: bash

    salt-call --local -lall mc_project.report


Deploy
~~~~~~~

The following lines edit the pillar, and push it, this does not trigger a deploy

.. code-block:: bash

    cd $WORKSPACE/myproject
    git clone host:/srv/projects/project/git/pillar.git
    $EDITOR pillar/init.sls
    cd pillar;git commit -am up;git push;cd ..

The following lines prepare a clone of your project codebase to be able to be
deployed onto production or staging servers

.. code-block:: bash

    cd $WORKSPACE/myproject
    git clone git@github.com/makinacorpus/myawsomeproject.git
    git remote add prod /srv/projects/project/git/project.git
    git fetch --all

To trigger a remote deployment, now you can do:

.. code-block:: bash

    git push [--force] prod <mybranch>:master
    eg: git push [--force] prod <mybranch>:master
    eg: git push [--force] prod awsome_feature:master

- **REMINDER**:
    - DONT MESS WITH THE **ORIGIN** REMOTE
    - The ``<branchname>:master`` is really important as everything in the production
      git repositories is wired on the master branch.
      You can push any branch you want from your original
      repository, but in production, there is only **master**.

Sumup
++++++++
To sum all that up, when beginning project you will:

- Initialize if not done a project structure with ``salt-call --local mc_project.init_project project``
- If you do not want git remotes, you can alternativly use ``salt-call --local mc_project.init_project project remote_less=False``
- add a **.salt** folder alongside your project codebase (in it's git repo).
- deploy it, either by:

    - git push your **pillar** files to ``host:/srv/projects/<project>/git/pillar.git``
    - git push your **project code** to ``host:/srv/projects/<project>/git/project.git``
      (this last push triggers a deploy on the remote server)

    - Your can use ``--force`` as the deploy system only await the ``.salt`` folder.
      As long as the folder is present of the working copy you are sending, the
      deploy system will be happy.

- or connected to the remote host to deploy onto

    - edit/commit/push in ``host:/srv/projects/<project>/pillar``
    - edit/commit/push/push to force in ``host:/srv/projects/<project>``
    - Launch the ``salt-call --local mc_project.deploy <name> only=install,fixperms,sync_modules`` dance

- Wash, Rince, Repeat

.. _project_configuration_pillar::

Configuration pillar &  variables
+++++++++++++++++++++++++++++++++
We provide in **mc_project** a powerfull mecanism to define default variables used in your deployments.
hat you can safely override in the salt pillar files.
This means that you can set some default values for, eg a domain name or a password, and input the production values that you won't commit along side your project codebase.

- Default values have to be stored inside the **PILLAR.sample** file.
- Some of those variables, the one at the first level are mostly read only and setup by makina-states itself.
  The most important are:

    - ``name``: project name
    - ``user``: the system user of your project
    - ``group``: the system group of your project
    - ``data``: top level free variables mapping
    - ``project_root``: project root absolute path
    - ``data_root``: persistent folder absolute path
    - ``default_env``: environment (staging/prod/dev)
    - ``pillar_root``: absolute path to the pillar
    - ``fqdn``: machine FQDN

- The only variables that you can edit at the first level are:

    - **remote_less**: is this project using git remotes for triggering deployments
    - **default_env**: environement (valid values are staging/dev/prod)
    - **env_defaults**: indexed by **env** dict that overloads data (pillar will still have the priority)
    - **os_defaults**: indexed by **os** dict that overloads data (pillar will still have the priority)

- The other variables, members of the **data** sub entry are free for you to add/edit.
- Any thing in the pillar ``pillar/init.sls`` overloads what is in ``project/.salt/PILLAR.sample``.

You can get and consult the result of the configuration assemblage like this::

    salt-call --local -ldebug mc_project.get_configuration <project_name>

.. _project_configuration_key::

- Remember that projects have a name, and the pillar key to configure and
  overload your project configuration is based on this key.

  If your project is name **foo**, you ll have to use **makina-projects.foo** in
  place of **makina-projects.example**.

Example

in ``project/.salt/PILLAR.sample``, you have:

.. code-block:: yaml

        makina-projects.projectname:
          data:
            start_cmd: 'myprog'


in ``pillar/init.sls``, you have:

.. code-block:: yaml

        makina-projects.foo:
           data:
             start_cmd: 'myprog2'

- In your states files, you can access the configuration via the magic
  ``opts.ms_project`` variable.
- In your modules or file templates, you can access the configuration via ``salt['mc_project.get_configuration'(name)``.
- A tip for loading the configuration from a template is doing something like that:

.. code-block:: yaml

    # project/.salt/00_deploy.sls
    {% set cfg = opts.ms_project %}
    toto:
      file.managed:
          - name: "source://makina-projects/{{cfg.name}}/files/etc/foo"
          - target: /etc/foo
          - user {{cfg.user}}
          - group {{cfg.user}}
          - defaults:
              project: {{cfg.name}}

    # project/.salt/files/etc/foo
    {% set cfg = opts.ms_project %}
    My Super Template of {{cfg.name}} will run {{cfg.data.start_cmd}}

What's happen when there is a deploy ?
---------------------------------------
- When you do a git push, you have the full procedure, see :ref:`spec doc <project_spec_deploy_proc>`
- When you use ``only=install,fixperms,sync_modules`` it only do some the :ref:`install <project_spec_proc_install>` & :ref:`fixperms <project_spec_proc_fixperms>` procedures.

Filesystem considerations
--------------------------
We use `POSIX Acls <http://en.wikipedia.org/wiki/Access_control_list#Filesystem_ACLs>`_ in
various places on your project folders.
At first, it feels a bit complicated, but it will enable you to smoothlessly edit your files or run
your programs with appropriate users without loosing security.

SaltStack integration
--------------------------
As you know in makina-states, there are 2 concurrent salt installs, one for **salt**, the one that you use,
and one for **mastersalt** for the devil ops.
In makina-states, we use by default:

- a virtualenv inside ``/salt-venv/salt``
- `salt from a fork <https://github.com/makina-corpus/salt.git>`_ installed inside ``/salt-venv/salt/src/salt``
- the salt file root resides, as usual, in ``/srv/salt``
- the salt pillar root resides, as usual, in ``/srv/pillar``
- the salt configuration root resides, as usual, in ``/etc/salt``

As you see, the project layout seems not integration on those following folders, but in fact, the project
initialisation routines made symlinks to integrate it which look like::

    /srv/salt/makina-projects/<project_name>>  -> /srv/projects/<project_name>/project§/.salt
    /srv/pillar/makina-projects/<project_name> -> /srv/projects/<project_name>/pillar

- The pillar is auto included in the **pillar top** (``/srv/pîllar/top.sls``).
- The project salt files are not and **must not** be included in the salt **top** for further highstates unless
  you know what you are doing.

You can unlink your project from salt with::

    salt-call --local -ldebug mc_project.unlink <project_name>

You can link project from salt with::

    salt-call --local -ldebug mc_project.link <project_name>

Related topics
---------------------
You can refer to :ref:`module_mc_project_2`


