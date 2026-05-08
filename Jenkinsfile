pipeline {
    agent any // Run this pipeline on any available executor

    stages {
        stage('Checkout Source Code') {
            steps {
                println 'Checking out source code from GitHub'
                checkout scm
            }
        }
    }
}