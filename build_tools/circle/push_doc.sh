#!/bin/bash
# This script is meant to be called in the "deploy" step defined in
# circle.yml. See https://circleci.com/docs/ for more details.
# The behavior of the script is controlled by environment variable defined
# in the circle.yml in the .circleci folder of the project.

# We have three possibily workflows:
#   If the git branch is 'master' then we want to commit and merge the dev/
#       docs on gh-pages
#   If the git branch is [0-9].[0.9]. (i.e. 0.9, 1.0, 1.0, 1.2) then we want to
#       commit and merge the major.minor/ docs on gh-pages
#   If the git branch is anything else then we just want to test that committing
#       the changes works so that problems can be debugged without needing to merge
#       to master

function git_fetch_commit {
    # Clone the pydicom repo, the checkout gh-pages, update the $DIR directory
    #   by deleting existing content and copying the most recent version from the
    #   $CIRCLE_BRANCH, then commit the changes with message $MSG
    MSG="Updating the docs in $DIR/ for branch: $CIRCLE_BRANCH, commit $CIRCLE_SHA1"

    # CircleCI version 2.0 builds the project in $HOME/project, i.e.:
    #   /home/circleci/project/pydicom/dataset.py
    # note the base directory for the repo is 'project' not 'pydicom'
    # DOC_REPO is set by the circle yaml file (currently 'pydicom')
    # Test to see if $HOME/pydicom exists, if not then clone it from the repo
    #   with CicleCI v2.0 this will always be the case
    cd $HOME
    if [ ! -d $CIRCLE_PROJECT_REPONAME ]
    then
        # Because this will be a new clone we can't use --depth 1 if we want
        #   to fetch/checkout gh-pages
        git clone $CIRCLE_REPOSITORY_URL
    fi

    cd $CIRCLE_PROJECT_REPONAME
    # We use sparecheckout to only checkout the directory we want to change
    git config core.sparsecheckout true
    echo $DIR > .git/info/sparse-checkout
    git fetch origin gh-pages
    git checkout gh-pages
    git reset --hard origin/gh-pages
    # Remove the existing document subdirectory and copy across the current version
    git rm -rf $DIR/ && rm -rf $DIR/
    cp -R $HOME/project/doc/_build/html $DIR
    git config --global user.email $EMAIL
    git config --global user.name $USERNAME
    git config --global push.default matching
    git add -f $DIR/
    git commit -m "$MSG" $DIR
}

# Test that the vars have been set
if [ -z ${CIRCLE_BRANCH+x} ]; then echo "CIRCLE_BRANCH is unset"; fi
if [ -z ${CIRCLE_SHA1+x} ]; then echo "CIRCLE_SHA1 is unset"; fi
if [ -z ${CIRCLE_WORKING_DIRECTORY+x} ]; then echo "CIRCLE_WORKING_DIRECTORY is unset"; fi
if [ -z ${CIRCLE_REPOSITORY_URL+x} ]; then echo "CIRCLE_REPOSITORY_URL is unset"; fi
if [ -z ${CIRCLE_PROJECT_REPONAME+x} ]; then echo "CIRCLE_PROJECT_REPONAME is unset"; fi
if [ -z ${HOME+x} ]; then echo "HOME is unset"; fi
if [ -z ${EMAIL+x} ]; then echo "EMAIL is unset"; fi
if [ -z ${USERNAME+x} ]; then echo "USERNAME is unset"; fi

# Determine which of the three workflows to take
if [ "$CIRCLE_BRANCH" = "master" ]
then
    # build of current master
    echo "Performing commit and push to $CIRCLE_PROJECT_REPONAME/gh-pages for $CIRCLE_BRANCH"
    # Changes are made to dev/ directory
    DIR=dev
    git_fetch_commit
    #git push origin gh-pages
    echo "Push complete"
elif [[ "$CIRCLE_BRANCH" =~ ^[0-9]+\.[0-9]+\.X$ ]]
then
    # build of release, matches branch name against 0.1.X, 91.235.X, etc
    echo "Performing commit and push to $CIRCLE_PROJECT_REPONAME/gh-pages for $CIRCLE_BRANCH"
    # Strip off .X from branch name, so changes will go to 0.1/, 91.235/, etc
    DIR="${CIRCLE_BRANCH::-2}"
    git_fetch_commit
    #git push origin gh-pages
    echo "Push complete"
else
    # build pull release, should be regex ^pull\/[0-9]+$ but lets run against
    #   everything that doesn't match the other two workflows
    echo "Testing commit only to $CIRCLE_PROJECT_REPONAME/gh-pages for $CIRCLE_BRANCH"
    # Changes are made to dev/ directory but not merged
    DIR=dev
    git_fetch_commit
    echo "Test complete, changes NOT pushed"
fi
