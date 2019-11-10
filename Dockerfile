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
ENV USER="user"
ENV HOME="/home/${USER}"
RUN useradd -ms /bin/bash $USER
USER $USER
WORKDIR $HOME

# clonning the bot repo and installing all the requirements
ENV BOT_DIR="${HOME}/delator"
ENV BOT_REPO="https://github.com/nogaems/delator.git"
RUN git clone $BOT_REPO $BOT_DIR
WORKDIR $BOT_DIR
RUN pip install --user -r requirements.txt

# copy configuration file you've preliminarily prepared
ADD config.py ./

CMD ["python main.py -l INFO"]
