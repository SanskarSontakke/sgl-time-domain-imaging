"""Referee-requested extension modules (Part VII of the referee report).

Every module here is additive: it imports the shipped spine (``sglsim``,
``expcommon``) and writes its OWN archive under ``results/`` named
``ext_<module>.npz`` / ``ext_<module>.json``.  No extension module writes into
``results/parts/`` or touches the fiducial archives, so the headline numbers of
the paper cannot be perturbed by an extension.

Run from the ``src/`` directory (the spine uses flat imports):

    cd src && python3 -m ext.fisher_bounds
    cd src && python3 -m ext.disk_kernel --nmax 96
"""
