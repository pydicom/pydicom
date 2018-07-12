#!/bin/bash
# This script is meant to be called in the "deploy" step defined in
# circle.yml. See https://circleci.com/docs/ for more details.
# The behavior of the script is controlled by environment variable defined
# in the circle.yml in the .circleci folder of the project.
# Test that the vars have been set
if [ -z ${CIRCLE_BRANCH+x} ]; then echo "CIRCLE_BRANCH is unset"; fi
if [ -z ${CIRCLE_SHA1+x} ]; then echo "CIRCLE_SHA1 is unset"; fi
if [ -z ${DOC_REPO+x} ]; then echo "DOC_REPO is unset"; fi
if [ -z ${ORGANIZATION+x} ]; then echo "ORGANIZATION is unset"; fi
if [ -z ${HOME+x} ]; then echo "HOME is unset"; fi
if [ -z ${EMAIL+x} ]; then echo "EMAIL is unset"; fi
if [ -z ${USERNAME+x} ]; then echo "USERNAME is unset"; fi

if [[ "$CIRCLE_BRANCH" =~ ^master$|^[0-9]+\.[0-9]+\.X$ ]]
then
  echo Pushing $CIRCLE_BRANCH to gh-pages branch...

  if [ "$CIRCLE_BRANCH" = "master" ]
  then
      dir=dev
  else
      # Strip off .X
      dir="${CIRCLE_BRANCH::-2}"
  fi

  MSG="Pushing the docs to $dir/ for branch: $CIRCLE_BRANCH, commit $CIRCLE_SHA1"

  cd $HOME
  if [ ! -d $DOC_REPO ];
  then git clone --depth 1 --no-checkout "git@github.com:"$ORGANIZATION"/"$DOC_REPO".git";
  fi
  cd $DOC_REPO
  git config core.sparseCheckout true
  echo $dir > .git/info/sparse-checkout
  git checkout gh-pages
  git reset --hard origin/gh-pages
  git rm -rf $dir/ && rm -rf $dir/
  cp -R $HOME/pydicom/doc/_build/html $dir
  git config --global user.email $EMAIL
  git config --global user.name $USERNAME
  git config --global push.default matching
  git add -f $dir/
  git commit -m "$MSG" $dir

  echo $MSG
  git push origin gh-pages

  echo "Done"

else
  # We run the git stuff (except the push) to check that it would've worked
  echo "Testing git clone and commit (but not push) for $CIRCLE_BRANCH"
  dir=dev

  cd $HOME
  if [ ! -d $DOC_REPO ];
  then git clone --depth 1 --no-checkout "git@github.com:"$ORGANIZATION"/"$DOC_REPO".git";
  fi
  cd $DOC_REPO
  git config core.sparseCheckout true
  echo $dir > .git/info/sparse-checkout
  git checkout gh-pages
  git reset --hard origin/gh-pages
  git rm -rf $dir/ && rm -rf $dir/
  cp -R $HOME/pydicom/doc/_build/html $dir
  git config --global user.email $EMAIL
  git config --global user.name $USERNAME
  git config --global push.default matching
  git add -f $dir/
  git commit -m "$MSG" $dir

  echo "Test complete, changes NOT pushed"
fi
