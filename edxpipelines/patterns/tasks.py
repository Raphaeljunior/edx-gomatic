from gomatic import *

from edxpipelines import constants


def generate_requirements_install(job, working_dir, runif="passed"):
    """
    Generates a command that runs:
    'sudo pip install -r requirements.txt'

    Args:
        job (gomatic.job.Job): the gomatic job which to add install requirements
        working_dir (str): the directory gocd should run the install command from
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                'sudo pip install -r requirements.txt'
            ],
            working_dir=working_dir,
            runif=runif
        )
    )


def generate_launch_instance(job, optional_override_files=[], runif="passed"):
    """
    Generate the launch AMI job. This ansible script generates 3 artifacts:
        key.pem             - Private key material generated for this instance launch
        launch_info.yml     - yaml file that contains information about the instance launched
        ansible_inventory   - a list of private aws IP addresses that can be fed in to ansible to run playbooks

    Args:
        job (gomatic.job.Job): the gomatic job which to add the launch instance task
        runif (str): one of ['passed', 'failed', 'any'] Default: passed
        optional_override_files (list): a list of additional override files to be passed to ansible.
                                        File path should be relative to the root directory the goagent will
                                        execute the job from
                                        The Ansible launch job takes some overrides provided by these files:
                                        https://github.com/edx/configuration/blob/master/playbooks/continuous_delivery/launch_instance.yml

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    job.ensure_artifacts(set([BuildArtifact('{}/key.pem'.format(constants.ARTIFACT_PATH)),
                             BuildArtifact('{}/ansible_inventory'.format(constants.ARTIFACT_PATH)),
                             BuildArtifact('{}/launch_info.yml'.format(constants.ARTIFACT_PATH))]))

    command = ' '.join(
        [
            'ansible-playbook ',
            '-vvvv ',
            '--module-path=playbooks/library ',
            '-i "localhost," ',
            '-c local ',
            '-e artifact_path=`/bin/pwd`/../{artifact_path} ',
            '-e base_ami_id=$BASE_AMI_ID ',
            '-e ec2_vpc_subnet_id=$EC2_VPC_SUBNET_ID ',
            '-e ec2_security_group_id=$EC2_SECURITY_GROUP_ID ',
            '-e ec2_instance_type=$EC2_INSTANCE_TYPE ',
            '-e ec2_instance_profile_name=$EC2_INSTANCE_PROFILE_NAME ',
            '-e ebs_volume_size=$EBS_VOLUME_SIZE ',
            '-e hipchat_token=$HIPCHAT_TOKEN ',
            '-e hipchat_room="$HIPCHAT_ROOM" ',
            '-e ec2_timeout=900 '
        ]
    )
    command = command.format(artifact_path=constants.ARTIFACT_PATH)
    for override_file in optional_override_files:
        command += ' -e @../{override_file} '.format(override_file=override_file)
    command += ' playbooks/continuous_delivery/launch_instance.yml'

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command
            ],
            working_dir=constants.PUBLIC_CONFIGURATION_DIR,
            runif=runif
        )
    )


def generate_create_ami(job, runif="passed", **kwargs):
    """
    TODO: Decouple AMI building and AMI tagging in to 2 different jobs/ansible scripts

    Args:
        job (gomatic.job.Job): the gomatic job which to add the launch instance task
        runif (str): one of ['passed', 'failed', 'any'] Default: passed
        **kwargs (dict):
            k,v pairs:
                k: the name of the option to pass to ansible
                v: the value to use for this option

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    job.ensure_artifacts(set([BuildArtifact('{}/ami.yml'.format(constants.ARTIFACT_PATH))]))
    command = ' '.join(
        [
            'ansible-playbook',
            '-vvvv',
            '--module-path=playbooks/library',
            '-i "localhost,"',
            '-c local',
            '-e @../{artifact_path}/launch_info.yml',
            '-e play=$PLAY',
            '-e deployment=$DEPLOYMENT',
            '-e edx_environment=$EDX_ENVIRONMENT',
            '-e app_repo=$APP_REPO',
            '-e configuration_repo=$CONFIGURATION_REPO',
            '-e configuration_version=$GO_REVISION_CONFIGURATION',
            '-e configuration_secure_repo=$CONFIGURATION_SECURE_REPO',
            '-e cache_id=$GO_PIPELINE_COUNTER',
            '-e ec2_region=$EC2_REGION',
            '-e artifact_path=`/bin/pwd`/../{artifact_path}',
            '-e hipchat_token=$HIPCHAT_TOKEN',
            '-e hipchat_room="$HIPCHAT_ROOM"',
            '-e ami_wait=$AMI_WAIT',
            '-e no_reboot=$NO_REBOOT',
            '-e extra_name_identifier=$GO_PIPELINE_COUNTER'
        ]
    )

    command = command.format(artifact_path=constants.ARTIFACT_PATH)
    for k, v in sorted(kwargs.items()):
        command += ' -e {key}={value} '.format(key=k, value=v)
    command += 'playbooks/continuous_delivery/create_ami.yml'

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command
            ],
            working_dir=constants.PUBLIC_CONFIGURATION_DIR,
            runif=runif
        )
    )


def generate_ami_cleanup(job, runif="passed"):
    """
    Use in conjunction with patterns.generate_launch_instance this will cleanup the EC2 instances and associated actions

    Args:
        job (gomatic.job.Job): the gomatic job which to add the launch instance task
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                'ansible-playbook '
                '-vvvv '
                '--module-path=playbooks/library '
                '-i "localhost," '
                '-c local '
                '-e @../{artifact_path}/launch_info.yml '
                '-e ec2_region=$EC2_REGION '
                '-e hipchat_token=$HIPCHAT_TOKEN '
                '-e hipchat_room="$HIPCHAT_ROOM" '
                'playbooks/continuous_delivery/cleanup.yml'.format(artifact_path=constants.ARTIFACT_PATH)
            ],
            working_dir=constants.PUBLIC_CONFIGURATION_DIR,
            runif=runif
        )
    )


def generate_run_migrations(job, sub_application_name=None, runif="passed"):
    """
    Generates GoCD task that runs migrations via an Ansible script.

    Assumes:
        - The play will be run using the continuous delivery Ansible config constants.ANSIBLE_CONTINUOUS_DELIVERY_CONFIG

    Args:
        job (gomatic.job.Job): the gomatic job to which the run migrations task will be added
        sub_application_name (str): additional command to be passed to the migrate app {cms|lms}
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    job.ensure_artifacts(
        set(
            [BuildArtifact('{}/migrations'.format(constants.ARTIFACT_PATH))]
        )
    )

    command = ' '.join(
        [
            'mkdir -p {artifact_path}/migrations;'
            'export ANSIBLE_HOST_KEY_CHECKING=False;'
            'export ANSIBLE_SSH_ARGS="-o ControlMaster=auto -o ControlPersist=30m";'
            'PRIVATE_KEY=`/bin/pwd`/../{artifact_path}/key.pem;'
            'ansible-playbook '
            '-vvvv '
            '-i ../{artifact_path}/ansible_inventory '
            '--private-key=$PRIVATE_KEY '
            '--module-path=playbooks/library '
            '--user=ubuntu '
            '-e APPLICATION_PATH=$APPLICATION_PATH '
            '-e APPLICATION_NAME=$APPLICATION_NAME '
            '-e APPLICATION_USER=$APPLICATION_USER '
            '-e ARTIFACT_PATH=`/bin/pwd`/../{artifact_path}/migrations '
            '-e DB_MIGRATION_USER=$DB_MIGRATION_USER '
            '-e DB_MIGRATION_PASS=$DB_MIGRATION_PASS '
        ]
    )

    command = command.format(artifact_path=constants.ARTIFACT_PATH)
    if sub_application_name is not None:
        command += '-e SUB_APPLICATION_NAME={sub_application_name} '.format(sub_application_name=sub_application_name)
    command += 'playbooks/continuous_delivery/run_migrations.yml'

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command
            ],
            working_dir=constants.PUBLIC_CONFIGURATION_DIR,
            runif=runif
        )
    )


def generate_check_migration_duration(job,
                                      input_file,
                                      duration_threshold,
                                      from_address,
                                      to_addresses,
                                      ses_region=None,
                                      runif='passed'):
    """
    Generates a task that checks a migration's duration against a threshold.
    If the threshold is exceeded, alert via email.

    Args:
        job (gomatic.Job): the Job to attach this stage to.
        input_file (str): Name of file containing migration duration.
        duration_threshold (int): Migration threshold in seconds.
        from_address (str): Single "From:" email address for alert email.
        to_addresses (list(str)): List of "To:" email addresses for alert email.
        ses_region (str): AWS region whose SES to use.
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)
    """
    cmd_args = [
        'python',
        'scripts/check_migrate_duration.py',
        '--migration_file',
        '../{artifact_path}/migrations/{input_file}'.format(
            artifact_path=constants.ARTIFACT_PATH,
            input_file=input_file
        ),
        '--duration_threshold', str(duration_threshold),
        '--instance_data',
        '${GO_SERVER_URL/:8154/}pipelines/${GO_PIPELINE_NAME}/${GO_PIPELINE_COUNTER}/${GO_STAGE_NAME}/${GO_STAGE_COUNTER}',
        '--from_address', from_address
    ]
    if ses_region:
        cmd_args.extend(('--aws_ses_region', ses_region))
    for email in to_addresses:
        cmd_args.extend(('--alert_email', email))

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                ' '.join(cmd_args)
            ],
            working_dir='tubular',
            runif=runif
        )
    )


def format_RSA_key(job, output_path, key):
    """
    Formats an RSA key for use in future jobs. Does not last between stages.
    Args:
        job (gomatic.job.Job): the gomatic job to which the task will be added
        output_path (str): The file to output the formatted key to.
        key (str): The RSA key to be formatted

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)
    """
    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                'touch {output_path} && '
                'chmod 600 {output_path} && '
                'python tubular/scripts/format_rsa_key.py --key "{key}" --output-file {output_path}'.format(
                    output_path=output_path, key=key
                )
            ]
        )
    )


def _fetch_secure_repo(job, secure_dir, secure_repo_envvar, secure_version_envvar, secure_repo_name, runif="passed"):
    """
    Setup a secure repo for use in providing secrets.

    Args:
        job (gomatic.job.Job): the gomatic job to which the task will be added
        secure_dir (str): name of dir containing the edx-ops/configuration-secure repo
        secure_repo_envvar (str): HTTPS-based link to secure repo on GitHub
        secure_version_envvar (str): GitHub ref identifying version of secure repo to use
        secure_repo_name (str): name of secure repo, e.g. "configuration-secure"
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                'touch github_key.pem && '
                'chmod 600 github_key.pem && '
                'python tubular/scripts/format_rsa_key.py --key "$PRIVATE_GITHUB_KEY" --output-file github_key.pem && '
                "GIT_SSH_COMMAND='/usr/bin/ssh -o StrictHostKeyChecking=no -i github_key.pem' "
                '/usr/bin/git clone ${secure_repo_envvar} {secure_dir} && '
                'cd {secure_dir} && '
                '/usr/bin/git checkout ${secure_version_envvar} && '
                '[ -d ../{artifact_path}/ ] && echo "Target Directory Exists" || mkdir ../{artifact_path}/ && '
                '/usr/bin/git rev-parse HEAD > ../{artifact_path}/{secure_repo_name}_sha'.format(
                    secure_dir=secure_dir,
                    secure_repo_envvar=secure_repo_envvar,
                    secure_version_envvar=secure_version_envvar,
                    secure_repo_name=secure_repo_name,
                    artifact_path=constants.ARTIFACT_PATH
                )
            ]
        )
    )


def generate_target_directory(job, directory_name=constants.ARTIFACT_PATH, runif="passed"):
    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                '[ -d {0} ] && echo "Directory Exists" || mkdir {0}'.format(directory_name)
            ],
            runif=runif
        )
    )


def fetch_secure_configuration(job, secure_dir, runif="passed"):
    """
    Setup the configuration-secure repo for use in providing secrets.

    Stage using this task must have the following environment variables:
        CONFIGURATION_SECURE_REPO
        CONFIGURATION_SECURE_VERSION

    Args:
        job (gomatic.job.Job): the gomatic job to which the playbook run task will be added
        secure_dir (str): name of dir containing the edx-ops/configuration-secure repo
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    return _fetch_secure_repo(
        job, secure_dir,
        "CONFIGURATION_SECURE_REPO",
        "CONFIGURATION_SECURE_VERSION",
        "configuration-secure"
    )


def fetch_gomatic_secure(job, secure_dir, runif="passed"):
    """
    Setup the gomatic-secure repo for use in providing secrets.

    Stage using this task must have the following environment variables:
        GOMATIC_SECURE_REPO
        GOMATIC_SECURE_VERSION
        PRIVATE_GITHUB_KEY

    Args:
        job (gomatic.job.Job): the gomatic job to which the task will be added
        secure_dir (str): name of dir containing the edx-ops/gomatic-secure repo
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    return _fetch_secure_repo(
        job, secure_dir,
        "GOMATIC_SECURE_REPO",
        "GOMATIC_SECURE_VERSION",
        "gomatic-secure"
    )


def fetch_edx_mktg(job, secure_dir, runif="passed"):
    """
    Setup the edx-mktg repo for use with Drupal deployment.

    Stage using this task must have the following environment variables:
        PRIVATE_MARKETING_REPOSITORY_URL
        MARKETING_REPOSITORY_VERSION

    Args:
        job (gomatic.job.Job): the gomatic job to which the task will be added
        secure_dir (str): name of dir containing the edx/edx-mktg repo
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)
    """
    return _fetch_secure_repo(
        job, secure_dir,
        "PRIVATE_MARKETING_REPOSITORY_URL",
        "MARKETING_REPOSITORY_VERSION",
        "edx-mktg"
    )


def generate_run_app_playbook(job, internal_dir, secure_dir, playbook_path, runif="passed", **kwargs):
    """
    Generates:
        a GoCD task that runs an Ansible playbook against a server inventory.

    Assumes:
        - The play will be run using the continuous delivery ansible config constants.ANSIBLE_CONTINUOUS_DELIVERY_CONFIG
        - The play will be run from the constants.PUBLIC_CONFIGURATION_DIR directory
        - a key file for this host in "{constants.ARTIFACT_PATH}/key.pem"
        - a ansible inventory file "{constants.ARTIFACT_PATH}/ansible_inventory"
        - a launch info file "{constants.ARTIFACT_PATH}/launch_info.yml"

    The calling pipline for this task must have the following materials:
        - edx-secure
        - configuration

        These are generated by edxpipelines.patterns.stages.generate_launch_instance

    Args:
        job (gomatic.job.Job): the gomatic job to which the playbook run task will be added
        secure_dir (str): name of dir containing the edx-ops/configuration-secure repo
        playbook_path (str): path to playbook relative to the top-level 'configuration' directory
        runif (str): one of ['passed', 'failed', 'any'] Default: passed
        **kwargs (dict):
            k,v pairs:
                k: the name of the option to pass to ansible
                v: the value to use for this option

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    command = ' '.join(
        [
            'chmod 600 ../{artifact_path}/key.pem;',
            'export ANSIBLE_HOST_KEY_CHECKING=False;',
            'export ANSIBLE_SSH_ARGS="-o ControlMaster=auto -o ControlPersist=30m";',
            'PRIVATE_KEY=$(/bin/pwd)/../{artifact_path}/key.pem;'
            'ansible-playbook',
            '-vvvv',
            '--private-key=$PRIVATE_KEY',
            '--user=ubuntu',
            '--module-path=playbooks/library ',
            '-i ../{artifact_path}/ansible_inventory '
            '-e @../{artifact_path}/launch_info.yml',
            '-e @../{internal_dir}/ansible/vars/${{DEPLOYMENT}}.yml',
            '-e @../{internal_dir}/ansible/vars/${{EDX_ENVIRONMENT}}-${{DEPLOYMENT}}.yml',
            '-e @../{secure_dir}/ansible/vars/${{DEPLOYMENT}}.yml',
            '-e @../{secure_dir}/ansible/vars/${{EDX_ENVIRONMENT}}-${{DEPLOYMENT}}.yml',
        ]
    )
    command = command.format(secure_dir=secure_dir, internal_dir=internal_dir, artifact_path=constants.ARTIFACT_PATH)
    for k, v in sorted(kwargs.items()):
        command += ' -e {key}={value} '.format(key=k, value=v)
    command += playbook_path

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command
            ],
            working_dir=constants.PUBLIC_CONFIGURATION_DIR,
            runif=runif
        )
    )


def generate_backup_drupal_database(job, site_env):
    """
    Creates a backup of the database in the given environment.

    Stage using this task must have the following environment variables:
        PRIVATE_ACQUIA_USERNAME
        PRIVATE_ACQUIA_PASSWORD

    Args:
        job (gomatic.job.Job): the gomatic job to which the task will be added
        site_env (str): The environment to clear caches from. Choose 'test' for stage and 'prod' for prod

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)
    """
    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                'python scripts/drupal_backup_database.py '
                '--env {site_env} '
                '--username $PRIVATE_ACQUIA_USERNAME '
                '--password $PRIVATE_ACQUIA_PASSWORD'.format(site_env=site_env)
            ],
            working_dir='tubular'
        )
    )


def generate_flush_drupal_caches(job, site_env):
    """
    Flushes all drupal caches
    Assumes the drupal root is located in edx-mktg/docroot. If changed, change the working dir.

    Args:
        job (gomatic.job.Job): the gomatic job to which the task will be added
        site_env (str): The environment to clear caches from. Choose 'test' for stage and 'prod' for prod

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)
    """
    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                'drush -y @edx.{site_env} cc all'.format(site_env=site_env)
            ],
            working_dir='edx-mktg/docroot'
        )
    )


def generate_clear_varnish_cache(job, site_env):
    """
    Clears the Varnish cache in the given environment.

    Stage using this task must have the following environment variables:
        PRIVATE_ACQUIA_USERNAME
        PRIVATE_ACQUIA_PASSWORD

    Args:
        job (gomatic.job.Job): the gomatic job to which the task will be added
        site_env (str): The environment to clear caches from. Choose 'test' for stage and 'prod' for prod

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)
    """
    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                'python scripts/drupal_clear_varnish.py '
                '--env {site_env} '
                '--username $PRIVATE_ACQUIA_USERNAME '
                '--password $PRIVATE_ACQUIA_PASSWORD'.format(site_env=site_env)
            ],
            working_dir='tubular'
        )
    )


def generate_drupal_deploy(job, site_env, tag_file):
    """
    Deploys the given tag to the environment.

    Stage using this task must have the following environment variables:
        PRIVATE_ACQUIA_USERNAME
        PRIVATE_ACQUIA_PASSWORD

    Expects there to be:
        - a text file containing the tag name in "{constants.ARTIFACT_PATH}/tag_file"

    Args:
        job (gomatic.job.Job): the gomatic job to which the task will be added
        site_env (str): The environment to clear caches from. Choose 'test' for stage and 'prod' for prod
        tag_file (str): The name of the file containing the name of the tag to deploy.

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)
    """
    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                'python scripts/drupal_deploy.py '
                '--env {site_env} '
                '--username $PRIVATE_ACQUIA_USERNAME '
                '--password $PRIVATE_ACQUIA_PASSWORD '
                '--tag $(cat ../{artifact_path}/{tag_file})'.format(site_env=site_env,
                                                                    tag_file=tag_file,
                                                                    artifact_path=constants.ARTIFACT_PATH)
            ],
            working_dir='tubular'
        )
    )


def generate_fetch_tag(job, site_env, path_name):
    """
    Fetches the name of the current tag deployed in the environment.

    Stage using this task must have the following environment variables:
        PRIVATE_ACQUIA_USERNAME
        PRIVATE_ACQUIA_PASSWORD

    Args:
        job (gomatic.job.Job): the gomatic job to which the task will be added
        site_env (str): The environment to clear caches from. Choose 'test' for stage and 'prod' for prod
        path_name (str): The path to write the tag names to.

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)
    """
    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                'python scripts/drupal_fetch_deployed_tag.py '
                '--env {site_env} '
                '--username $PRIVATE_ACQUIA_USERNAME '
                '--password $PRIVATE_ACQUIA_PASSWORD '
                '--path_name {path_name}'.format(site_env=site_env, path_name=path_name)
            ],
            working_dir='tubular'
        )
    )


def generate_refresh_metadata(job, runif='passed'):
    """
    Generates GoCD task that refreshes metadata (for the Catalog Service) via an Ansible script.

    Args:
        job (gomatic.job.Job): the gomatic job to which the run migrations task will be added
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    command = ' '.join(
        [
            'export ANSIBLE_HOST_KEY_CHECKING=False;',
            'export ANSIBLE_SSH_ARGS="-o ControlMaster=auto -o ControlPersist=30m";',
            'PRIVATE_KEY=`/bin/pwd`/../../key.pem;',
            'ansible-playbook',
            '-vvvv',
            '-i ../../ansible_inventory',
            '--private-key=$PRIVATE_KEY',
            '--user=ubuntu',
            '-e APPLICATION_PATH=$APPLICATION_PATH',
            '-e APPLICATION_NAME=$APPLICATION_NAME',
            '-e APPLICATION_USER=$APPLICATION_USER',
            '-e HIPCHAT_TOKEN=$HIPCHAT_TOKEN',
            '-e HIPCHAT_ROOM="$HIPCHAT_ROOM"',
            'discovery_refresh_metadata.yml',
        ]
    )

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command
            ],
            working_dir='configuration/playbooks/continuous_delivery/',
            runif=runif
        )
    )


def generate_update_index(job, runif='passed'):
    """
    Generates GoCD task that runs the Haystack update_index management command via an Ansible script.

    Args:
        job (gomatic.job.Job): the gomatic job to which the run migrations task will be added
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    command = ' '.join(
        [
            'export ANSIBLE_HOST_KEY_CHECKING=False;',
            'export ANSIBLE_SSH_ARGS="-o ControlMaster=auto -o ControlPersist=30m";',
            'PRIVATE_KEY=`/bin/pwd`/../../key.pem;',
            'ansible-playbook',
            '-vvvv',
            '-i ../../ansible_inventory',
            '--private-key=$PRIVATE_KEY',
            '--user=ubuntu',
            '-e APPLICATION_PATH=$APPLICATION_PATH',
            '-e APPLICATION_NAME=$APPLICATION_NAME',
            '-e APPLICATION_USER=$APPLICATION_USER',
            '-e HIPCHAT_TOKEN=$HIPCHAT_TOKEN',
            '-e HIPCHAT_ROOM="$HIPCHAT_ROOM"',
            'haystack_update_index.yml',
        ]
    )

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command
            ],
            working_dir='configuration/playbooks/continuous_delivery/',
            runif=runif
        )
    )


def generate_create_release_candidate_branch_and_pr(job,
                                                    org,
                                                    repo,
                                                    source_branch,
                                                    target_branch,
                                                    pr_target_branch,
                                                    runif='passed'):
    """
    Assumptions:
        Assumes a secure environment variable named "GIT_TOKEN"

    Args:
        job (gomatic.Job): the Job to attach this stage to.
        org (str): Name of the github organization that holds the repository (e.g. edx)
        repo (str): Name of repository (e.g edx-platform)
        source_branch (str): Name of the branch to create the branch/PR from
        target_branch (str): Name of the branch to be created (will be the head of the PR)
        pr_target_branch (str): The base branch of the pull request (merge target_branch in to pr_target_branch)
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    command = ' '.join(
        [
            'python',
            'scripts/create_release_candidate.py',
            '--org {org}',
            '--repo {repo}',
            '--source_branch {source_branch}',
            '--target_branch {target_branch}',
            '--pr_target_branch {pr_target_branch}',
            '--token $GIT_TOKEN'
        ]
    )

    command = command.format(
        org=org,
        repo=repo,
        source_branch=source_branch,
        target_branch=target_branch,
        pr_target_branch=pr_target_branch
    )

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command
            ],
            working_dir='tubular',
            runif=runif
        )
    )


def generate_create_branch(job,
                           org,
                           repo,
                           target_branch,
                           runif='passed',
                           source_branch=None,
                           sha=None):
    """
    Assumptions:
        Assumes a secure environment variable named "GIT_TOKEN"

    Args:
        job (gomatic.Job): the Job to attach this stage to.
        org (str): Name of the github organization that holds the repository (e.g. edx)
        repo (str): Name of repository (e.g edx-platform)
        target_branch (str): Name of the branch to be created (will be the head of the PR)
        runif (str): one of ['passed', 'failed', 'any'] Default: passed
        source_branch (str): Name (or environment variable) of the branch to create the branch/PR from
        sha (str): SHA (or environment variable) of the commit to create the branch/PR from

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    command = [
        'python',
        'scripts/cut_branch.py',
        '--org', org,
        '--repo', repo,
        '--target_branch', target_branch,
        '--token', '$GIT_TOKEN',
        '--output_file', '../{artifact_path}/{output_file}'.format(
            artifact_path=constants.ARTIFACT_PATH,
            output_file=constants.CREATE_BRANCH_FILENAME
        )
    ]

    if source_branch:
        command.extend(['--source_branch', source_branch])

    if sha:
        command.extend(['--sha', sha])

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                ' '.join(command),
            ],
            working_dir='tubular',
            runif=runif
        )
    )


def generate_create_pr(job,
                       org,
                       repo,
                       source_branch,
                       target_branch,
                       title,
                       body,
                       runif='passed'):
    """
    Assumptions:
        Assumes a secure environment variable named "GIT_TOKEN"

    Args:
        job (gomatic.Job): the Job to attach this stage to.
        org (str): Name of the github organization that holds the repository (e.g. edx)
        repo (str): Name of repository (e.g edx-platform)
        source_branch (str): Name of the branch to create the branch/PR from
        target_branch (str): Name of the branch to be created (will be the head of the PR)
        title (str): Title to use for the created PR
        body (str): Body to use for the created PR
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)
    """
    output_file_path = '{}/{}'.format(
        constants.ARTIFACT_PATH,
        constants.CREATE_BRANCH_PR_FILENAME
    )
    job.ensure_artifacts(set([BuildArtifact(output_file_path)]))

    cmd_args = [
        'python',
        'scripts/create_pr.py',
        '--org {org}',
        '--repo {repo}',
        '--source_branch {source_branch}',
        '--target_branch {target_branch}',
        '--title "{title}"',
        '--body "{body}"',
        '--token $GIT_TOKEN',
        '--output_file ../{output_file_path}'
    ]
    command = ' '.join(cmd_args)

    command = command.format(
        org=org,
        repo=repo,
        source_branch=source_branch,
        target_branch=target_branch,
        title=title,
        body=body,
        output_file_path=output_file_path
    )

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command
            ],
            working_dir='tubular',
            runif=runif
        )
    )


def generate_merge_branch(job,
                          org,
                          repo,
                          source_branch,
                          target_branch,
                          fast_forward_only,
                          runif='passed'):
    """
    Assumptions:
        Assumes a secure environment variable named "GIT_TOKEN"

    Args:
        job (gomatic.Job): the Job to attach this stage to.
        org (str): Name of the github organization that holds the repository (e.g. edx)
        repo (str): Name of repository (e.g edx-platform)
        source_branch (str): Name of the branch to merge into the target branch
        target_branch (str): Name of the branch into which to merge the source branch
        fast_forward_only (bool): If True, force a fast-forward merge or fail.
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    output_file_path = '{}/{}'.format(
        constants.ARTIFACT_PATH,
        constants.MERGE_BRANCH_FILENAME
    )
    job.ensure_artifacts(set([BuildArtifact(output_file_path)]))

    cmd_args = [
        'python',
        'scripts/merge_branch.py',
        '--org {org}',
        '--repo {repo}',
        '--source_branch {source_branch}',
        '--target_branch {target_branch}',
        '--output_file ../{output_file_path}'
    ]
    if fast_forward_only:
        cmd_args.append('--fast_forward_only')
    command = ' '.join(cmd_args)

    command = command.format(
        org=org,
        repo=repo,
        source_branch=source_branch,
        target_branch=target_branch,
        output_file_path=output_file_path
    )

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command
            ],
            working_dir='tubular',
            runif=runif
        )
    )


def generate_merge_pr(job,
                      org,
                      repo,
                      input_file,
                      runif='passed'):
    """
    Assumptions:
        Assumes a secure environment variable named "GIT_TOKEN"

    Args:
        job (gomatic.Job): the Job to attach this stage to.
        org (str): Name of the github organization that holds the repository (e.g. edx)
        repo (str): Name of repository (e.g edx-platform)
        input_file (str): Path to YAML file containing PR number, using "pr_id" key
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)
    """
    cmd_args = [
        'python',
        'scripts/merge_pr.py',
        '--org {org}',
        '--repo {repo}',
        '--input_file ../{artifact_path}/{input_file}',
        '--token $GIT_TOKEN',
    ]
    command = ' '.join(cmd_args)

    command = command.format(
        org=org,
        repo=repo,
        artifact_path=constants.ARTIFACT_PATH,
        input_file=input_file,
    )

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command
            ],
            working_dir='tubular',
            runif=runif
        )
    )


def generate_tag_commit(job,
                        org,
                        repo,
                        input_file=None,
                        commit_sha=None,
                        branch_name=None,
                        deploy_artifact_filename=None,
                        tag_name=None,
                        tag_message=None,
                        runif='passed'):
    """
    Generates a task that tags a commit SHA, passed in these ways:
    - input YAML file containing a 'sha' key
    - explicitly passed-in commit SHA
    - HEAD sha obtained from passed-in branch_name

    Assumptions:
        Assumes a secure environment variable named "GIT_TOKEN"

    Args:
        job (gomatic.Job): the Job to attach this stage to.
        org (str): Name of the github organization that holds the repository (e.g. edx)
        repo (str): Name of repository (e.g edx-platform)
        input_file (str): Name of file containing commit SHA.
        commit_sha (str): Commit SHA to tag.
        branch_name (str): Branch name whose HEAD will be tagged.
        deploy_artifact_filename (str): Filename of the deploy artifact.
        tag_name (str): Name to use for the commit tag.
        tag_message (str): Message to use for the commit tag.
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    cmd_args = [
        'python',
        'scripts/create_tag.py',
        '--org', org,
        '--repo', repo,
        '--token $GIT_TOKEN',
    ]
    if input_file:
        cmd_args.append('--input_file ../{artifact_path}/{input_file}'.format(
            artifact_path=constants.ARTIFACT_PATH,
            input_file=input_file
        ))
    if commit_sha:
        cmd_args.extend(('--commit_sha', commit_sha))
    if branch_name:
        cmd_args.extend(('--branch_name', branch_name))
    if tag_name:
        cmd_args.extend(('--tag_name', tag_name))
    if tag_message:
        cmd_args.extend(('--tag_message', tag_message))
    if deploy_artifact_filename:
        cmd_args.append('--deploy_artifact ../{artifact_path}/{deploy_artifact_filename}'.format(
            artifact_path=constants.ARTIFACT_PATH,
            deploy_artifact_filename=deploy_artifact_filename
        ))

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                ' '.join(cmd_args)
            ],
            working_dir='tubular',
            runif=runif
        )
    )


def generate_check_pr_tests(job,
                            org,
                            repo,
                            input_file,
                            runif='passed'):
    """
    Assumptions:
        Assumes a secure environment variable named "GIT_TOKEN"

    Args:
        job (gomatic.Job): the Job to attach this stage to.
        org (str): Name of the github organization that holds the repository (e.g. edx)
        repo (str): Name of repository (e.g edx-platform)
        input_file (str): Name of YAML file containing PR id.
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    cmd_args = [
        'python',
        'scripts/check_pr_tests_status.py',
        '--org {org}',
        '--repo {repo}',
        '--input_file ../{artifact_path}/{input_file}',
        '--token $GIT_TOKEN',
    ]
    command = ' '.join(cmd_args)

    command = command.format(
        org=org,
        repo=repo,
        artifact_path=constants.ARTIFACT_PATH,
        input_file=input_file,
    )

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command
            ],
            working_dir='tubular',
            runif=runif
        )
    )


def generate_poll_pr_tests(job,
                           org,
                           repo,
                           input_file,
                           runif='passed'):
    """
    Assumptions:
        Assumes a secure environment variable named "GIT_TOKEN"

    Args:
        job (gomatic.Job): the Job to attach this stage to.
        org (str): Name of the github organization that holds the repository (e.g. edx)
        repo (str): Name of repository (e.g edx-platform)
        input_file (str): Name of YAML file containing PR id.
        runif (str): one of ['passed', 'failed', 'any'] Default: passed

    Returns:
        The newly created task (gomatic.gocd.tasks.ExecTask)

    """
    cmd_args = [
        'python',
        'scripts/poll_pr_tests_status.py',
        '--org {org}',
        '--repo {repo}',
        '--input_file ../{artifact_path}/{input_file}',
        '--token $GIT_TOKEN',
    ]
    command = ' '.join(cmd_args)

    command = command.format(
        org=org,
        repo=repo,
        artifact_path=constants.ARTIFACT_PATH,
        input_file=input_file,
    )

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                command,
            ],
            working_dir='tubular',
            runif=runif
        )
    )


def trigger_jenkins_build(
        job, jenkins_url, jenkins_user_name, jenkins_job_name,
        jenkins_params, timeout=30 * 60
):
    """
    Generate a GoCD task that triggers a jenkins build and polls for its results.

    Assumes:
        secure environment variables:
            - JENKINS_USER_TOKEN: API token for the user. Available at {url}/user/{user_name)/configure
            - JENKINS_JOB_TOKEN: Authorization token for the job. Must match that configured in the job definition.

    Args:
        job (gomatic.job.Job): the gomatic job to which this task will be added
        jenkins_url (str): base URL for the jenkins server
        jenkins_user_name (str): username on the jenkins system
        jenkins_job_name (str): name of the jenkins job to trigger
        jenkins_param (dict): parameter names and values to pass to the job
    """
    command = [
        'python ',
        'scripts/jenkins_trigger_build.py',
        '--url {}'.format(jenkins_url),
        '--user_name {}'.format(jenkins_user_name),
        '--job {}'.format(jenkins_job_name),
        '--cause "Triggered by GoCD Pipeline ${GO_PIPELINE_NAME} build ${GO_PIPELINE_LABEL}"',
        '--timeout', str(timeout)
    ]
    command.extend(
        '--param {} {}'.format(name, value)
        for name, value in jenkins_params.items()
    )

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                ' '.join(command)
            ],
            working_dir='tubular',
        )
    )


def _generate_message_pull_requests_in_commit_range(
        job, org, repo, token, head_sha, message_type,
        runif='passed', base_sha=None, base_ami_artifact=None, ami_tag_app=None
):
    """
    Generate a GoCD task that will message a set of pull requests within a range of commits.

    If base_sha is not supplied, then base_ami_artifact and ami_tag_app must both be supplied.

    Args:
        job (gomatic.job.Job): the gomatic job to which this task will be added
        org (str): The github organization
        repo (str): The github repository
        token (str): The authentication token
        head_sha (str): The ending SHA
        message_type (str): type of message to send one of ['release_stage', 'release_prod', 'release_rollback']
        runif (str): one of ['passed', 'failed', 'any'] Default: passed
        base_sha (str): The sha to use as the base point for sending messages
            (any commits prior to this sha won't be messaged). (Optional)
        base_ami_artifact (ArtifactLocation): The location of the artifact that specifies
            the base_ami and tags (Optional)
        ami_tag_app (str): The name of the version tag on the AMI to extract the version from (Optional)


    Returns:
        gomatic.task.Task
    """
    command = [
        'python ',
        'scripts/message_prs_in_range.py',
        '--org', org,
        '--token', token,
        '--repo', repo,
        '--head_sha', head_sha,
        '--{}'.format(message_type)
    ]
    if base_sha:
        command.extend(['--base_sha', base_sha])

    if base_ami_artifact and ami_tag_app:
        job.add_task(
            FetchArtifactTask(
                pipeline=base_ami_artifact.pipeline,
                stage=base_ami_artifact.stage,
                job=base_ami_artifact.job,
                src=FetchArtifactFile(base_ami_artifact.file_name),
                dest=constants.ARTIFACT_PATH,
            )
        )

        command.extend([
            '--base_ami_tags', "../{}/{}".format(constants.ARTIFACT_PATH, base_ami_artifact.file_name),
            '--ami_tag_app', ami_tag_app,
        ])
    elif base_ami_artifact or ami_tag_app:
        raise ValueError(
            "Both base_ami_artifact ({!r}) and ami_tag_app"
            "({!r}) must be specified together".format(
                base_ami_artifact, ami_tag_app
            )
        )

    return job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                ' '.join(command),
            ],
            working_dir='tubular',
        )
    )


def generate_message_prs_stage(
    job, org, repo, token, head_sha, runif='passed',
    base_sha=None, base_ami_artifact=None, ami_tag_app=None
):
    """
    Generate a GoCD task that will message a set of pull requests within a range of commits that their commit has been
    deployed to the staging environment.

    If base_sha is not supplied, then base_ami_artifact and ami_tag_app must both be supplied.

    Args:
        job (gomatic.job.Job): the gomatic job to which this task will be added
        org (str): The github organization
        repo (str): The github repository
        token (str): The authentication token
        head_sha (str): The ending SHA
        runif (str): one of ['passed', 'failed', 'any'] Default: passed
        base_sha (str): The sha to use as the base point for sending messages
            (any commits prior to this sha won't be messaged). (Optional)
        base_ami_artifact (ArtifactLocation): The location of the artifact that specifies
            the base_ami and tags (Optional)
        ami_tag_app (str): The name of the version tag on the AMI to extract the version from (Optional)


    Returns:
        gomatic.task.Task
    """
    _generate_message_pull_requests_in_commit_range(
        job, org, repo, token, head_sha, 'release_stage',
        runif, base_ami_artifact=base_ami_artifact, ami_tag_app=ami_tag_app
    )


def generate_message_prs_prod(
    job, org, repo, token, head_sha, runif='passed',
    base_sha=None, base_ami_artifact=None, ami_tag_app=None
):
    """
    Generate a GoCD task that will message a set of pull requests within a range of commits that their commit has been
    deployed to the production environment.

    If base_sha is not supplied, then base_ami_artifact and ami_tag_app must both be supplied.

    Args:
        job (gomatic.job.Job): the gomatic job to which this task will be added
        org (str): The github organization
        repo (str): The github repository
        token (str): The authentication token
        head_sha (str): The ending SHA
        runif (str): one of ['passed', 'failed', 'any'] Default: passed
        base_sha (str): The sha to use as the base point for sending messages
            (any commits prior to this sha won't be messaged). (Optional)
        base_ami_artifact (ArtifactLocation): The location of the artifact that specifies
            the base_ami and tags (Optional)
        ami_tag_app (str): The name of the version tag on the AMI to extract the version from (Optional)

    Returns:
        gomatic.task.Task
    """
    _generate_message_pull_requests_in_commit_range(
        job, org, repo, token, head_sha, 'release_prod',
        runif, base_ami_artifact=base_ami_artifact, ami_tag_app=ami_tag_app
    )


def generate_message_prs_rollback(
    job, org, repo, token, head_sha, runif='passed',
    base_sha=None, base_ami_artifact=None, ami_tag_app=None
):
    """
    Generate a GoCD task that will message a set of pull requests within a range of commits that their commit has been
    rolled back from the production environment.

    If base_sha is not supplied, then base_ami_artifact and ami_tag_app must both be supplied.

    Args:
        job (gomatic.job.Job): the gomatic job to which this task will be added
        org (str): The github organization
        repo (str): The github repository
        token (str): The authentication token
        head_sha (str): The ending SHA
        runif (str): one of ['passed', 'failed', 'any'] Default: passed
        base_sha (str): The sha to use as the base point for sending messages
            (any commits prior to this sha won't be messaged). (Optional)
        base_ami_artifact (ArtifactLocation): The location of the artifact that specifies
            the base_ami and tags (Optional)
        ami_tag_app (str): The name of the version tag on the AMI to extract the version from (Optional)

    Returns:
        gomatic.task.Task
    """
    _generate_message_pull_requests_in_commit_range(
        job, org, repo, token, head_sha, 'release_rollback',
        runif, base_ami_artifact=base_ami_artifact, ami_tag_app=ami_tag_app
    )
