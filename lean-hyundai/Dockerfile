FROM quantconnect/lean:latest

USER root

# hd_core 는 make_signals(컨테이너 안)와 웹앱 백엔드(컨테이너 밖) 양쪽에서 import 됩니다.
COPY hd_core.py /module/hd_core.py
COPY make_signals.py /module/make_signals.py
COPY make_report.py /module/make_report.py
COPY download_price_data.py /module/download_price_data.py
COPY HyundaiMLStrategy.py /module/HyundaiMLStrategy.py
COPY config.json /module/config.json
COPY entrypoint.sh /module/entrypoint.sh

RUN chmod +x /module/entrypoint.sh \
    && mkdir -p /results

# make_signals.py 가 같은 폴더의 hd_core 를 찾도록 합니다.
ENV PYTHONPATH=/module

ENTRYPOINT ["/module/entrypoint.sh"]
