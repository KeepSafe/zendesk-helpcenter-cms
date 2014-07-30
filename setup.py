import os
from setuptools import setup

version = '0.0.1'


def read(f):
    return open(os.path.join(os.path.dirname(__file__), f)).read().strip()


setup(name='zendesk-helpcenter-cms',
      version=version,
      description=('Zendesk helpcenter CMS'),
      long_description='\n\n'.join((read('README.md'), read('CHANGELOG'))),
      classifiers=[
          'License :: OSI Approved :: BSD License',
          'Intended Audience :: Developers',
          'Programming Language :: Python'],
      author='Keepsafe',
      author_email='support@getkeepsafe.com',
      url='https://github.com/KeepSafe/zendesk-helpcenter-cms/',
      license='Apache',
      py_modules=['translator'],
      namespace_packages=[],
      install_requires = ['Markdown==2.4.1', 'html2text==2014.7.3', 'requests==2.3.0'],
      entry_points={
          'console_scripts': [
              'kzt = translator:main']
      },
      include_package_data = False)
