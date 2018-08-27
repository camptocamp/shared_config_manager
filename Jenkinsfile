#!groovy
@Library('c2c-pipeline-library')
import static com.camptocamp.utils.*

final IMAGES_BASE_NAME = 'camptocamp/shared_config_manager'

// make sure we don't mess with another build by using latest on both
env.IN_CI = '1'

dockerBuild {
    stage('Update docker') {
        checkout scm
        sh 'make clean pull'
    }
    stage('Build') {
        checkout scm
        parallel 'Main': {
            sh 'make -j2 build'
        }, 'Tests': {
            sh 'make -j2 build_acceptance'
        }
    }
    stage('Test') {
        checkout scm
        try {
            lock("acceptance-${env.NODE_NAME}") {  //only one acceptance test at a time on a machine
                sh 'make -j2 acceptance'
            }
        } finally {
            junit keepLongStdio: true, testResults: 'reports/*.xml'
        }
    }

    if (env.BRANCH_NAME == 'master') {
        stage("Publish master") {
            //push them
            withCredentials([[$class          : 'UsernamePasswordMultiBinding', credentialsId: 'dockerhub',
                              usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD']]) {
                sh 'docker login -u "$USERNAME" -p "$PASSWORD"'
                docker.image("${IMAGES_BASE_NAME}:latest").push()
                sh 'rm -rf ~/.docker*'
            }
        }
    }
}
