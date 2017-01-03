from gomatic import BuildArtifact, ExecTask

from edxpipelines import constants
from edxpipelines.patterns import tasks

def generate_base_ami_selection(pipeline,
                                stage,
                                aws_access_key_id,
                                aws_secret_access_key,
                                play,
                                deployment,
                                edx_environment,
                                base_ami_id,
                                base_ami_id_override='no'
                                ):
    """
    Pattern to find a base AMI for a particular EDP. Generates 1 artifact:
        ami_override.yml    - YAML file that contains information about which base AMI to use in building AMI

    Args:
        pipeline (gomatic.Pipeline):
        stage (gomatic.Stage):
        aws_access_key_id (str): AWS key ID for auth
        aws_secret_access_key (str): AWS secret key for auth
        play (str): Pipeline's play.
        deployment (str): Pipeline's deployment.
        edx_environment (str): Pipeline's environment.
        base_ami_id (str): the ami-id used to launch the instance
        base_ami_id_override (str): "yes" to use the base_ami_id provided,
                                    any other value to extract the base AMI ID from the provided EDP instead

    Returns:
        gomatic.Job
    """
    pipeline.ensure_encrypted_environment_variables(
        {
            'AWS_ACCESS_KEY_ID': aws_access_key_id,
            'AWS_SECRET_ACCESS_KEY': aws_secret_access_key
        }
    )

    pipeline.ensure_environment_variables(
        {
            'PLAY': play,
            'DEPLOYMENT': deployment,
            'EDX_ENVIRONMENT': edx_environment,
            'BASE_AMI_ID': base_ami_id,
            'BASE_AMI_ID_OVERRIDE': base_ami_id_override,
        }
    )

    # Install the requirements.
    job = stage.ensure_job(constants.BASE_AMI_SELECTION_JOB_NAME)
    tasks.generate_requirements_install(job, 'tubular')

    # Generate an base-AMI-ID-overriding artifact.
    base_ami_override_artifact = '{artifact_path}/{file_name}'.format(
        artifact_path=constants.ARTIFACT_PATH,
        file_name=constants.BASE_AMI_OVERRIDE_FILENAME
    )
    job.ensure_artifacts(set([BuildArtifact(base_ami_override_artifact)]))
    job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                'mkdir -p {artifact_path};'
                'if [ $BASE_AMI_ID_OVERRIDE != \'yes\' ];'
                '  then echo "Finding base AMI ID from active ELB/ASG in EDP.";'
                '  /usr/bin/python {ami_script} --environment $EDX_ENVIRONMENT --deployment $DEPLOYMENT --play $PLAY --out_file {override_artifact};'
                'elif [ $BASE_AMI_ID != \'\' ];'
                '  then echo "Using specified base AMI ID of \'$BASE_AMI_ID\'";'
                '  echo "base_ami_id: $BASE_AMI_ID" > {override_artifact};'
                'else echo "Using environment base AMI ID";'
                '  echo "{empty_dict}" > {override_artifact}; fi;'.format(
                    artifact_path='../' + constants.ARTIFACT_PATH,
                    ami_script='scripts/retrieve_base_ami.py',
                    empty_dict='{}',
                    override_artifact='../' + base_ami_override_artifact
                )
            ],
            working_dir="tubular",
            runif="passed"
        )
    )

    return job


def generate_versions_manifest(stage):
    """
    Pattern to capture all versions. Generates 1 artifact:
        versions.yml:     YAML file that contains all SCM Material revision environment variables

    Args:
        stage (gomatic.Stage):

    Returns:
        gomatic.Job
    """

    # Install the requirements.
    job = stage.ensure_job(constants.VERSION_MANIFEST_JOB_NAME)

    # Generate an base-AMI-ID-overriding artifact.
    version_manifest_path = '{artifact_path}/{file_name}'.format(
        artifact_path=constants.ARTIFACT_PATH,
        file_name=constants.VERSION_MANIFEST_ARTIFACT_NAME
    )
    job.ensure_artifacts(set([BuildArtifact(version_manifest_path)]))
    job.add_task(
        ExecTask(
            [
                '/bin/bash',
                '-c',
                'mkdir -p {artifact_path};'
                'echo "---" > {version_manifest_path} && '
                'env | grep -E "GO_(FROM|TO)" | sed "s/=/: /" >> {version_manifest_path}'.format(
                    artifact_path='../' + constants.ARTIFACT_PATH,
                    version_manifest_path='../' + version_manifest_path,
                )
            ],
            working_dir="tubular",
            runif="passed"
        )
    )
    return job
