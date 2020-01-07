FROM python:3

# installing olm and python-olm
ENV OLM_REPO="https://gitlab.matrix.org/matrix-org/olm.git"
RUN git clone $OLM_REPO
WORKDIR olm
RUN make install
WORKDIR python
RUN python setup.py install
RUN ldconfig

# adding a user to run the bot from
ARG TARGET_USER="user"
ARG TARGET_UID="1000"
ARG HOME="/home/${TARGET_USER}"
RUN useradd -u $TARGET_UID -ms /bin/bash $TARGET_USER
USER $TARGET_USER
WORKDIR $HOME

# clonning the bot repo and installing all the requirements
ENV BOT_DIR="${HOME}/delator"
ENV BOT_REPO="https://github.com/nogaems/delator.git"
# here's a workaround to disable cache
ARG NO_CACHE=`date`
RUN git clone $BOT_REPO $BOT_DIR
WORKDIR $BOT_DIR
RUN pip install --user -r requirements.txt

# copy configuration file you've preliminarily prepared
ADD config.py ./
USER root
RUN chown $TARGET_UID:$TARGET_UID ./config.py
RUN chmod 600 ./config.py
USER $TARGET_USER

CMD python main.py -l INFO
