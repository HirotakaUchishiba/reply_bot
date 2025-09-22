Place Presidio Python packages under this directory as a Python Lambda layer.

Suggested structure:

layers/
  presidio/
    python/
      lib/python3.11/site-packages/
        presidio_analyzer/
        presidio_anonymizer/
        ...

Build example:

pip install presidio-analyzer presidio-anonymizer -t layers/presidio/python/lib/python3.11/site-packages
