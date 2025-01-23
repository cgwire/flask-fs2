=========
Flask-FS2
=========

Simple and easy file storages for Flask.

|CI badge|


Compatibility
=============

Flask-FS requires Python >= 3.9 and Flask/Werkzeug >= 2.0.0.

Amazon S3 support requires Boto3.

GridFS support requires PyMongo 3+.

OpenStack Swift support requires python-swift-client.


Installation
============

You can install Flask-FS with pip:

.. code-block:: console

    $ pip install flask-fs2
    # or
    $ pip install flask-fs2[s3]  # For Amazon S3 backend support
    $ pip install flask-fs2[swift]  # For OpenStack swift backend support
    $ pip install flask-fs2[gridfs]  # For GridFS backend support
    $ pip install flask-fs2[all]  # To include all dependencies for all backends


Quick start
===========

.. code-block:: python

    from flask import Flask
    import flask_fs as fs

    app = Flask(__name__)
    fs.init_app(app)

    images = fs.Storage('images')


    if __name__ == '__main__':
        app.run(debug=True)


Contributions
=============

All contributions are welcome as long as they respect the `C4
contract <https://rfc.zeromq.org/spec:42/C4>`__.

Code must follow the pep8 convention.

About authors
=============

Flask-FS2 is maintained by CGWire, a company based in France. We help animation 
and VFX studios to collaborate better through efficient tooling. 
We already work with more than 70 studios around the world.

It's a fork of `this project <https://github.com/noirbizarre/flask-fs>`__.

Visit `cg-wire.com <https://cg-wire.com>`__ for more information.

|CGWire Logo|

.. |CI badge| image:: https://github.com/cgwire/flask-fs2/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/cgwire/flask-fs2/actions/workflows/ci.yml
.. |CGWire Logo| image:: https://zou.cg-wire.com/cgwire.png
   :target: https://cg-wire.com
