pipeline {
    agent any

    tools {
        gradle 'Gradle-8'
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
    }

    parameters {
        string(name: 'APP_VERSION', defaultValue: '', description: 'Optional release version. Blank = Jenkins BUILD_NUMBER.')
        booleanParam(name: 'PUSH_IMAGE', defaultValue: false, description: 'Push the Docker image to Docker Hub using the dockerhub-creds credential.')
    }

    environment {
        DOCKER_IMAGE = 'leave-approval-system'
        IMAGE_TAG = "${BUILD_NUMBER}"
    }

    triggers {
        pollSCM('H/5 * * * *')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Gradle Build & Unit Tests') {
            steps {
                script {
                    def releaseVersion = params.APP_VERSION?.trim() ? params.APP_VERSION.trim() : env.BUILD_NUMBER
                    if (isUnix()) {
                        sh "gradle --no-daemon clean build -PappVersion=${releaseVersion}"
                    } else {
                        bat "gradle --no-daemon clean build -PappVersion=${releaseVersion}"
                    }
                }
            }
        }

        stage('Archive Build Artifact') {
            steps {
                archiveArtifacts artifacts: 'build/dist/*.zip', fingerprint: true
            }
        }

        stage('Selenium Quality Gate') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'gradle --no-daemon seleniumTest'
                    } else {
                        bat 'gradle --no-daemon seleniumTest'
                    }
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            set -e
                            docker build -t "$DOCKER_IMAGE:$IMAGE_TAG" -t "$DOCKER_IMAGE:latest" .
                        '''
                    } else {
                        bat '''
                            docker build -t "%DOCKER_IMAGE%:%IMAGE_TAG%" -t "%DOCKER_IMAGE%:latest" .
                        '''
                    }
                }
            }
        }

        stage('Publish Docker Image') {
            when {
                expression { params.PUSH_IMAGE }
            }
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-creds',
                    usernameVariable: 'DOCKERHUB_USER',
                    passwordVariable: 'DOCKERHUB_TOKEN'
                )]) {
                    script {
                        if (isUnix()) {
                            sh '''
                                set -e
                                echo "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USER" --password-stdin
                                docker tag "$DOCKER_IMAGE:$IMAGE_TAG" "$DOCKERHUB_USER/$DOCKER_IMAGE:$IMAGE_TAG"
                                docker tag "$DOCKER_IMAGE:latest" "$DOCKERHUB_USER/$DOCKER_IMAGE:latest"
                                docker push "$DOCKERHUB_USER/$DOCKER_IMAGE:$IMAGE_TAG"
                                docker push "$DOCKERHUB_USER/$DOCKER_IMAGE:latest"
                                docker logout
                            '''
                        } else {
                            bat '''
                                echo %DOCKERHUB_TOKEN%| docker login -u "%DOCKERHUB_USER%" --password-stdin
                                docker tag "%DOCKER_IMAGE%:%IMAGE_TAG%" "%DOCKERHUB_USER%/%DOCKER_IMAGE%:%IMAGE_TAG%"
                                docker tag "%DOCKER_IMAGE%:latest" "%DOCKERHUB_USER%/%DOCKER_IMAGE%:latest"
                                docker push "%DOCKERHUB_USER%/%DOCKER_IMAGE%:%IMAGE_TAG%"
                                docker push "%DOCKERHUB_USER%/%DOCKER_IMAGE%:latest"
                                docker logout
                            '''
                        }
                    }
                }
            }
        }

        stage('Deploy Nginx Stack') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            set -e
                            export IMAGE_TAG="$IMAGE_TAG"
                            export DOCKER_IMAGE="$DOCKER_IMAGE"
                            docker compose up -d --build
                            docker compose ps
                            curl --fail --retry 10 --retry-delay 2 http://127.0.0.1:8000/health
                        '''
                    } else {
                        bat '''
                            set IMAGE_TAG=%IMAGE_TAG%
                            set DOCKER_IMAGE=%DOCKER_IMAGE%
                            docker compose up -d --build
                            docker compose ps
                            powershell -NoProfile -Command "$r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health; if ($r.StatusCode -ne 200) { exit 1 }"
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: false, testResults: 'build/test-results/*.xml'
            archiveArtifacts allowEmptyArchive: true, artifacts: 'test-results/screenshots/**/*'
        }
        success {
            echo 'Employee Leave Approval CI/CD pipeline completed successfully.'
            echo 'Application URL: http://localhost:8000/dashboard'
        }
    }
}
