#!/usr/bin/python
# Copyright (c) 2013 Qubell Inc., http://qubell.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import shutil

from os.path import join
from optparse import OptionParser


def main():
    parser = OptionParser(usage="usage: %prog [options]", version="%prog 0.1")
    parser.add_option("-d", "--dir", dest="dir",
                      action="store",
                      type="string",
                      help="component folder")
    parser.add_option("-n", "--new", dest="new",
                      action="store_true",
                      default=False,
                      help="generate new skeleton for component")

    (options, args) = parser.parse_args()

    if options.new:
        new(options.dir)
    else:
        parser.print_help(sys.stderr)
        parser.exit(2, "\n%s: error: %s\n" % (parser.get_prog_name(), "please enter options"))


def new(component_dir):
    skeleton_dir = os.path.dirname(__file__)

    if not component_dir:
        component_dir = join(skeleton_dir, "../")
    else:
        component_dir = os.path.realpath(component_dir)

    test_dir = join(component_dir, "test")

    mkdir_p(test_dir)

    build_sh_path = join(component_dir, 'build.sh')

    write(build_sh_path, build_sh(test_dir))
    write(join(component_dir, ".travis.yml"), travis_template(test_dir))
    write(join(test_dir, "test_example.py"), template_test())

    copy(join(skeleton_dir, "test_runner.py"), join(test_dir, "test_runner.py"))
    copy(join(skeleton_dir, "requirements.txt"), join(test_dir, "requirements.txt"))

    chmod_x(build_sh_path)


def chmod_x(path):
    import stat

    file_stat = os.stat(path)
    os.chmod(path, file_stat.st_mode | stat.S_IEXEC)


def copy(path, target):
    if not os.path.exists(target):
        shutil.copy2(path, target)
    else:
        print '%s already exist' % path


def write(path, content):
    if not os.path.exists(path):
        with open(path, 'a') as file:
            file.write(content)
    else:
        print '%s already exist' % path


def mkdir_p(target_dir):
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)


def travis_template(test_dir):
    return """env:
 global:

    ## Fill environment variables:
    ## (You may secure your keys using: http://about.travis-ci.org/docs/user/encryption-keys/)

    - "QUBELL_TENANT=https://express.qubell.com"
    ## QUBELL_USER, QUBELL_PASSWORD 
    ## - These are for Qubell authentication, use user with Basic auth

    ## PROVIDER_NAME, PROVIDER_TYPE, PROVIDER_REGION, PROVIDER_IDENTITY, PROVIDER_CREDENTIAL
    ## - These are for Cloud Account setting, when you need to provision virtual machines
    ## - Identity and Credential must be secured

    ## ARTIFACTS_AWS_REGION, ARTIFACTS_S3_BUCKET, ARTIFACTS_AWS_ACCESS_KEY_ID, ARTIFACTS_AWS_SECRET_ACCESS_KEY
    ## - These are for publishing Cookbooks
    ## - Access Key Id and Secret Access Key must be secured

    ## GIT_NAME, GIT_EMAIL, GH_TOKEN
    ## - These are for push back to github of verified cookbooks
    ## - All must be secured

language: python
python:
  - "2.7"

install: "pip install -r %(test_dir)s/requirements.txt"

before_script:
   - gem install travis-artifacts --no-ri --no-rdoc
   - git submodule update --init --recursive

script: ./build.sh
""" % {"test_dir": os.path.basename(test_dir)}


def build_sh(test_dir):
    return """#!/bin/bash

REPO_NAME=$(echo ${TRAVIS_REPO_SLUG} | cut -d/ -f2)
OWNER_NAME=$(echo ${TRAVIS_REPO_SLUG} | cut -d/ -f1)
GIT_REVISION=$(git log --pretty=format:'%h' -n 1)
LAST_COMMIT_AUTHOR=$(git log --pretty=format:'%an' -n1)

function check {
    "$@"
    status=$?
    if [ $status -ne 0 ]; then
        echo "error run $@"
        exit $status
    fi
    return $status
}

function package {
    local REVISION=$1

    tar -czf ${REPO_NAME}-cookbooks-${REVISION}.tar.gz cookbooks
}

function publish {
    local REVISION=$1

    package $REVISION

    travis-artifacts upload --path ${REPO_NAME}-cookbooks-${REVISION}.tar.gz --target-path ${OWNER_NAME}/
}

function replace {
    local REVISION=$1

    check sed -i.bak -e 's/'${REPO_NAME}'-cookbooks-stable-[[:alnum:]]*.tar.gz/'${REPO_NAME}'-cookbooks-'${REVISION}'.tar.gz/g' ${REPO_NAME}.yml
    cat ${REPO_NAME}.yml
}

function publish_github {
    GIT_URL=$(git config remote.origin.url)
    NEW_GIT_URL=$(echo $GIT_URL | sed -e 's/^git:/https:/g' | sed -e 's/^https:\/\//https:\/\/'${GH_TOKEN}':@/')

    git remote rm origin
    git remote add origin ${NEW_GIT_URL}
    git fetch -q
    git config user.name ${GIT_NAME}
    git config user.email ${GIT_EMAIL}
    rm -rf *.tar.gz
    git commit -a -m "CI: Success build ${TRAVIS_BUILD_NUMBER} [skip ci]"
    git checkout -b build
    git push -q origin build:master
}

if [[ ${TRAVIS_PULL_REQUEST} == "false" ]]; then
    if [[ ${LAST_COMMIT_AUTHOR} != "CI" ]]; then
        publish "stable-${GIT_REVISION}"
        replace "stable-${GIT_REVISION}"

        pushd test

        check python test_runner.py

        popd

        publish_github
    fi
fi
"""


def template_test():
    return """import os

from test_runner import BaseComponentTestCase
from qubell.api.private.testing import instance, environment, workflow, values


@environment({
    "default": {}
})
class ComponentTestCase(BaseComponentTestCase):
    name = "name-component"
    apps = [{
        "name": name,
        "file": os.path.realpath(os.path.join(os.path.dirname(__file__), '../%s.yml' % name))
    }]

    def test_fail(self):
        assert Fail, "Test is not implemented, start to write your tests here"

    def test_pass(self):
        assert True, "Just another test, that passes"
"""


if __name__ == "__main__":
    main()
