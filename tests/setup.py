import setuptools

if __name__ == '__main__':
    setuptools.setup(
        name='qvctests',
        version='1.0',
        author='Invisible Things Lab',
        author_email='marmarek@invisiblethingslab.com',
        description='QVC tests',
        license='MIT',
        url='https://www.qubes-os.org/',
        packages=['qvctests'],
        entry_points={
            'qubes.tests.extra.for_template':
                'qvctests = qvctests.integ:list_tests',
        }
    )
