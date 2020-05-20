from setuptools import setup, find_packages

readme = open('README.md').read()
history = open('HISTORY.md').read()
reqs = [x.strip() for x in open('requirements.txt').readlines()]

setup(
    name='race',
    version='0.0.1',
    author='Andrey Cizov',
    author_email='acizov@gmail.com',
    packages=find_packages(include=('race', 'race.*',)),
    description='Race condition modelling package',
    keywords='',
    url='https://github.com/andreycizov/python-race',
    include_package_data=True,
    long_description=readme,
    install_requires=reqs,
    entry_points={
    },
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
    ]
)
