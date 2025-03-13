from setuptools import setup

package_name = 'af_configurator'

setup(
    name=package_name,
    version='0.1.4',
    packages=[package_name],
    include_package_data=True,
    package_data={
        package_name: ['resource/cyclonedds/cyclonedds.xsd',
                       'resource/template/**/*']
    },
    install_requires=[
        'PyYaml',
        'xmlschema',
        'xmltodict',
        'numpy',
        'openpyxl', # for compatible with numpy 1.19.3
        'jinja2'
    ],
    zip_safe=True,
    maintainer='jiaqi.li1',
    maintainer_email='jiaqi.li1@hirain.com',
    description='AF RED configurator tools',
    license='Hirain License',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'af_config = {}.{}:matrix_to_af_red_source_code'.format(
                package_name, 'main'),
            'af_app_create = {}.{}:af_red_config_to_source_code'.format(
                package_name, 'main'),
            'simulink_app_create = {}.{}:af_red_config_to_simulink_source_code'.format(
                package_name, 'main'),
            'dds_bridge_config = {}.{}:matrix_to_cyclonedds_config'.format(
                package_name, 'main'),
        ],
    },
)
