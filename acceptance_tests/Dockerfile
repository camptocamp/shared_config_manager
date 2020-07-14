FROM camptocamp/c2cwsgiutils:release_4

WORKDIR /acceptance_tests

RUN apt update
RUN apt install --assume-yes git

COPY requirements.txt ./
RUN python3 -m pip install --disable-pip-version-check --no-cache-dir --requirement=requirements.txt && \
  rm --recursive --force /tmp/*

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --clear && \
  rm --recursive --force /usr/local/lib/python3.8/dist-packages/tests/ /tmp/* /root/.cache/*

COPY . ./

RUN ./create-test-repos
RUN prospector

VOLUME [ "/repos", "/config" ]

CMD py.test -vv --color=yes --junitxml /reports/acceptance.xml acceptance
