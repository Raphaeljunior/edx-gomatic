from gomatic import *

import edxpipelines.constants as constants
import edxpipelines.patterns.tasks as tasks


def generate_rollback_migration(stage,
                                inventory_location,
                                instance_key_location,
                                migration_info_location,
                                sub_application_name=None
                                ):
    job_name = constants.ROLLBACK_MIGRATIONS_JOB_NAME
    if sub_application_name is not None:
        job_name += "_{}".format(sub_application_name)
    job = stage.ensure_job(job_name)

    # Fetch the Ansible inventory to use in reaching the EC2 instance.
    artifact_params = {
        "pipeline": inventory_location.pipeline,
        "stage": inventory_location.stage,
        "job": inventory_location.job,
        "src": FetchArtifactFile(inventory_location.file_name),
        "dest": constants.ARTIFACT_PATH
    }
    job.add_task(FetchArtifactTask(**artifact_params))

    # Fetch the SSH key to use in reaching the EC2 instance.
    artifact_params = {
        "pipeline": instance_key_location.pipeline,
        "stage": instance_key_location.stage,
        "job": instance_key_location.job,
        "src": FetchArtifactFile(instance_key_location.file_name),
        "dest": constants.ARTIFACT_PATH
    }
    job.add_task(FetchArtifactTask(**artifact_params))

    # ensure the target directoy exists
    tasks.generate_target_directory(job)

    # fetch the migration outputs
    artifact_params = {
        "pipeline": migration_info_location.pipeline,
        "stage": migration_info_location.stage,
        "job": migration_info_location.job,
        "src": FetchArtifactDir(migration_info_location.file_name),
        "dest": constants.ARTIFACT_PATH
    }
    job.add_task(FetchArtifactTask(**artifact_params))

    # The SSH key used to access the EC2 instance needs specific permissions.
    job.add_task(
        ExecTask(
            ['/bin/bash', '-c', 'chmod 600 {}'.format(instance_key_location.file_name)],
            working_dir=constants.ARTIFACT_PATH
        )
    )

    tasks.generate_requirements_install(job, 'configuration')
    tasks.generate_migration_rollback(job, sub_application_name)
