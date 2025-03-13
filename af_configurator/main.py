import argparse

from af_configurator import dds_matrix_to_af_red
from af_configurator import app_creator
from af_configurator.app_creator import SimulinkAppCreator
from af_configurator import dds_bridge


def matrix_to_af_red_source_code():
    dds_matrix_to_af_red.main()


def matrix_to_cyclonedds_config():
    dds_bridge.main()


def af_red_config_to_source_code():
    app_creator.main()


def af_red_config_to_simulink_source_code():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='input package dir', type=str)
    parser.add_argument('--name', default='HAV3G_TDA4MultiThreads', help='input model file name', type=str)
    parser.add_argument('--type', default='EU260_MultiThreadsModelClass', help='input class name', type=str)
    args = parser.parse_args()

    package_dir = args.input
    model_name = args.name
    model_class = args.type
    app_creator = SimulinkAppCreator()
    app_creator.create_from_dir(package_dir, model_name, model_class)


if __name__ == '__main__':
    # matrix_to_af_red_source_code()
    # af_red_config_to_simulink_source_code()
    dds_bridge.main()
