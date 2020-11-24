# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
Convenience functions for `astropy.cosmology`.
"""

import warnings
import numpy as np

from .core import CosmologyError
from astropy.units import Quantity

__all__ = ['z_at_value']

__doctest_requires__ = {'*': ['scipy']}


def z_at_value(func, fval, zmin=1e-8, zmax=1000, ztol=1e-8, maxfun=500,
               method='Brent', bracket=None, verbose=False):
    """ Find the redshift ``z`` at which ``func(z) = fval``.

    This finds the redshift at which one of the cosmology functions or
    methods (for example Planck13.distmod) is equal to a known value.

    .. warning::
      Make sure you understand the behavior of the function that you
      are trying to invert! Depending on the cosmology, there may not
      be a unique solution. For example, in the standard Lambda CDM
      cosmology, there are two redshifts which give an angular
      diameter distance of 1500 Mpc, z ~ 0.7 and z ~ 3.8. To force
      ``z_at_value`` to find the solution you are interested in, use the
      ``zmin`` and ``zmax`` keywords to limit the search range (see the
      example below).

    Parameters
    ----------
    func : function or method
       A function that takes a redshift as input.
    fval : `~astropy.units.Quantity` instance
       The (scalar) value of ``func(z)`` to recover.
    zmin : float, optional
       The lower search limit for ``z``.  Beware of divergences
       in some cosmological functions, such as distance moduli,
       at z=0 (default 1e-8).
    zmax : float, optional
       The upper search limit for ``z`` (default 1000).
    ztol : float, optional
       The relative error in ``z`` acceptable for convergence.
    maxfun : int, optional
       The maximum number of function evaluations allowed in the
       optimization routine (default 500).
    method : str or callable, optional
       Type of solver to pass to ``~scipy.optimize.minimize_scalar`` -
       should be one of 'Brent' (default), 'Golden' or 'Bounded'.
       Can in theory also be a callable object as custom solver,
       but this is untested.
    bracket : sequence, optional
       For methods 'Brent' and 'Golden', ``bracket`` defines the bracketing
       interval and can either have three items (z1, z2, z3) so that z1 < z2 < z3
       and ``func(z2) < func(z1), func(z3)`` or two items z1 and z3 which are
       assumed to be a starting interval for a downhill bracket search.
       For bimodal functions such as angular diameter distance this can be
       used to start the search on the desired side of the maximum.
    verbose : bool, optional
       Print diagnostic output from solver (default `False`).

    Returns
    -------
    z : float
      The redshift ``z`` satisfying ``zmin < z < zmax`` and ``func(z) =
      fval`` within ``ztol``.

    Notes
    -----
    This works for any arbitrary input cosmology, but is inefficient
    if you want to invert a large number of values for the same
    cosmology. In this case, it is faster to instead generate an array
    of values at many closely-spaced redshifts that cover the relevant
    redshift range, and then use interpolation to find the redshift at
    each value you're interested in. For example, to efficiently find
    the redshifts corresponding to 10^6 values of the distance modulus
    in a Planck13 cosmology, you could do the following:

    >>> import astropy.units as u
    >>> from astropy.cosmology import Planck13, z_at_value

    Generate 10^6 distance moduli between 24 and 43 for which we
    want to find the corresponding redshifts:

    >>> Dvals = (24 + np.random.rand(1000000) * 20) * u.mag

    Make a grid of distance moduli covering the redshift range we
    need using 50 equally log-spaced values between zmin and
    zmax. We use log spacing to adequately sample the steep part of
    the curve at low distance moduli:

    >>> zmin = z_at_value(Planck13.distmod, Dvals.min())
    >>> zmax = z_at_value(Planck13.distmod, Dvals.max())
    >>> zgrid = np.logspace(np.log10(zmin), np.log10(zmax), 50)
    >>> Dgrid = Planck13.distmod(zgrid)

    Finally interpolate to find the redshift at each distance modulus:

    >>> zvals = np.interp(Dvals.value, Dgrid.value, zgrid)

    Examples
    --------
    >>> import astropy.units as u
    >>> from astropy.cosmology import Planck13, z_at_value

    The age and lookback time are monotonic with redshift, and so a
    unique solution can be found:

    >>> z_at_value(Planck13.age, 2 * u.Gyr)  # doctest: +FLOAT_CMP
    3.19812268

    The angular diameter is not monotonic however, and there are two
    redshifts that give a value of 1500 Mpc. Use the zmin and zmax keywords
    to find the one you're interested in:

    >>> z_at_value(Planck13.angular_diameter_distance,
    ...            1500 * u.Mpc, zmax=1.5)  # doctest: +FLOAT_CMP
    0.6812769577
    >>> z_at_value(Planck13.angular_diameter_distance,
    ...            1500 * u.Mpc, zmin=2.5)  # doctest: +FLOAT_CMP
    3.7914913242

    Also note that the luminosity distance and distance modulus (two
    other commonly inverted quantities) are monotonic in flat and open
    universes, but not in closed universes.
    """
    from scipy.optimize import minimize_scalar

    opt = {'maxiter': maxfun}
    if method.lower() == 'bounded':
        opt['xatol'] = ztol
        if bracket is not None:
            warnings.warn(f"Option 'bracket' is ignored by method {method}.")
    else:
        opt['xtol'] = ztol

    fval_zmin = func(zmin)
    fval_zmax = func(zmax)
    if np.sign(fval - fval_zmin) != np.sign(fval_zmax - fval):
        warnings.warn(f"fval is not bracketed by func(zmin)={fval_zmin} and func(zmax)="
                      f"{fval_zmax}. This means either there is no solution, or that there is "
                      "more than one solution between zmin and zmax satisfying fval = func(z).")

    if isinstance(fval_zmin, Quantity):
        val = fval.to_value(fval_zmin.unit)
    else:
        val = fval

    # 'Brent' and 'Golden' ignore `bounds`, force solution inside zlim
    def f(z):
        if zmin <= z <= zmax:
            return abs(Quantity(func(z)).value - val)
        else:
            return 1.e300

    res = minimize_scalar(f, method=method, bounds=(zmin, zmax), bracket=bracket, options=opt)

    if not res['success']:
        warnings.warn(f"Solver returned {res['status']}: {res['message']}\n"
                      f"Precision {res['fun']} reached after {res['nfev']} function calls.")

    if verbose:
        print(res)

    zbest = max(min(res['x'], zmax), zmin)
    if np.allclose(zbest, zmax):
        raise CosmologyError(f"Best guess z={zbest} is very close to the upper z limit {zmax}.\n"
                             "Try re-running with a different zmax.")
    elif np.allclose(zbest, zmin):
        raise CosmologyError(f"Best guess z={zbest} is very close to the lower z limit {zmin}.\n"
                             "Try re-running with a different zmin.")
    return zbest
