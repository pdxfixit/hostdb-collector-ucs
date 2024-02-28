FROM python:3.8-alpine

LABEL maintainer="Ben Sandberg <info@pdxfixit.com>" \
      name="hostdb-collector-ucs" \
      vendor="PDXfixIT, LLC"

RUN /usr/local/bin/pip install pyyaml requests ucsmsdk

WORKDIR /opt/hostdb-collector-ucs
COPY config.yaml hostdb-collector-ucs.py ./

CMD [ "hostdb-collector-ucs.py" ]
ENTRYPOINT [ "/usr/local/bin/python3" ]
