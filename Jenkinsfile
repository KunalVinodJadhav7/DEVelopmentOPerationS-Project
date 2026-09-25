pipeline {
    agent any

    parameters {
        choice(
            name: 'DEPLOY_ENV',
            choices: ['staging', 'production'],
            description: 'Deployment environment'
        )
    }

    environment {
        PYTHON_EXE  = 'C:\\Users\\kphvj\\AppData\\Local\\Programs\\Python\\Python313\\python.exe'
        DEPLOY_ROOT = 'C:\\ProgramData\\Jenkins\\deploy\\leaveflow'
        APP_PORT    = '8000'
    }

    triggers {
        pollSCM('H/5 * * * *')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    stages {

        stage('GitHub Checkout') {
            steps {
                deleteDir()

                echo 'Checking out Employee Leave Approval System from GitHub...'

                git(
                    branch: 'main',
                    credentialsId: 'github-credentials',
                    url: 'https://github.com/KunalVinodJadhav7/DEVelopmentOPerationS-Project.git'
                )

                bat 'git log -1 --oneline'
                bat 'dir'
            }
        }

        stage('Python Setup') {
            steps {
                echo 'Creating Python CI environment...'

                bat '''
                    "%PYTHON_EXE%" -m venv .ci-venv
                    .ci-venv\\Scripts\\python.exe -m pip install --upgrade pip
                    .ci-venv\\Scripts\\python.exe -m pip install -r requirements.txt
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                echo 'Running Python unit tests...'

                bat '''
                    if not exist build\\test-results mkdir build\\test-results

                    .ci-venv\\Scripts\\python.exe -m pytest tests -q --junitxml=build\\test-results\\pytest-jenkins.xml
                '''
            }

            post {
                always {
                    junit(
                        testResults: 'build/test-results/pytest-jenkins.xml',
                        allowEmptyResults: true
                    )
                }
            }
        }

        stage('Gradle Build') {
            steps {
                echo 'Running Gradle build and packaging...'

                bat '''
                    where gradle
                    gradle --version
                    gradle --no-daemon clean build "-PappVersion=1.0.%BUILD_NUMBER%"
                '''
            }
        }

        stage('Verify Artifact') {
            steps {
                echo 'Verifying generated ZIP artifact...'

                bat '''
                    if not exist build\\dist (
                        echo ERROR: build\\dist directory was not created.
                        exit /b 1
                    )

                    dir build\\dist

                    if not exist build\\dist\\*.zip (
                        echo ERROR: ZIP artifact was not created.
                        exit /b 1
                    )

                    echo ZIP artifact successfully created.
                '''
            }
        }

        stage('Archive ZIP Artifact') {
            steps {
                echo 'Archiving ZIP artifact in Jenkins...'

                archiveArtifacts(
                    artifacts: 'build/dist/*.zip',
                    fingerprint: true
                )
            }
        }

        // Add deployment stages here if required.
    }

    post {
        success {
            echo 'Jenkins CI completed successfully.'
            echo 'Checkout, Python setup, unit tests, Gradle build, ZIP packaging, and artifact archiving succeeded.'
        }

        failure {
            echo 'Jenkins CI failed. Check the failed stage in the Jenkins console output.'
        }
    }
}
