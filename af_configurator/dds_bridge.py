import argparse
import os
import yaml

from .dds_matrix_to_af_red import AfConfigurator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='input dds matrix excel/xml',
                        default='hav25-dds-dp.xlsx', type=str)
    parser.add_argument('-o', '--output', help='output folder',
                        default='test_bridge_output', type=str)
    parser.add_argument('--interfaces', help='interfaces package name',
                        default='hav_interfaces', type=str)
    args = parser.parse_args()

    hav_25_dds_matrix = AfConfigurator(
        args.input, args.output, args.interfaces)
    for ecu in hav_25_dds_matrix.ecus:
        if '397' in ecu.name:
            continue
        ecu_dir = os.path.join(args.output, ecu.name)
        os.makedirs(ecu_dir, exist_ok=True)
        for app in ecu.apps.values():
            # domain_id -> domain_config
            app_filename = os.path.join(ecu_dir, app.name + '.yaml')
            domain_dic = {}
            for dp in app.domain_participants:
                domain_id = dp.domain.id
                if domain_id not in domain_dic:
                    domain_dic[domain_id] = {'id': domain_id,
                                             'participants': []}
                dp_dic = {'name': dp.name,
                          'id': dp.participant_id,
                          'publishers': [],
                          'subscribers': []}
                for pub in dp.publishers:
                    pub_dic = {'name': pub.name,
                               'topics': []}
                    topics = {}
                    for dw in pub.data_writers:
                        topic_name = dw.topic.name
                        print(topic_name)
                        if not hav_25_dds_matrix.parser.check_pub_topic_is_with_397(topic_name):
                            continue
                        if topic_name not in topics:
                            topics[topic_name] = {'topic_name': topic_name,
                                                  'data_type': dw.topic.type,
                                                  'datawriters': []}
                        dw_dic = {'name': dw.name,
                                  'qos': dw.qos.get_config()}
                        topics[topic_name]['datawriters'].append(dw_dic)
                    pub_dic['topics'] = [t for t in topics.values()]
                    dp_dic['publishers'].append(pub_dic)
                for sub in dp.subscribers:
                    sub_dic = {'name': sub.name,
                               'topics': []}
                    topics = {}
                    for dr in sub.data_readers:
                        topic_name = dr.topic.name
                        if not hav_25_dds_matrix.parser.check_sub_topic_is_with_397(topic_name):
                            continue
                        if topic_name not in topics:
                            topics[topic_name] = {'topic_name': topic_name,
                                                  'data_type': dr.topic.type,
                                                  'datareaders': []}
                        dr_dic = {'name': dr.name,
                                  'qos': dr.qos.get_config()}
                        topics[topic_name]['datareaders'].append(dr_dic)
                    sub_dic['topics'] = [t for t in topics.values()]
                    dp_dic['subscribers'].append(sub_dic)
                domain_dic[domain_id]['participants'].append(dp_dic)
                app_config = {'Domains': [d for d in domain_dic.values()]}
            with open(app_filename, 'w') as f:
                f.write(yaml.dump(app_config))

    hav_25_dds_matrix.generate_dds_idl()


if __name__ == '__main__':
    main()
