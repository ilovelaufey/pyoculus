## @file fixed_point.py
#  @brief class for finding fixed points
#  @author Zhisong Qu (zhisong.qu@anu.edu.au)
#

from .base_solver import BaseSolver
from pyoculus.problems.cylindrical_problem import CylindricalProblem
from pyoculus.problems.toroidal_problem import ToroidalProblem
import numpy as np

## Class that used to setup the fixed point finder.
class FixedPoint(BaseSolver):
    def __init__(
        self, problem, params=dict(), integrator=None, integrator_params=dict(), evolve_axis=True
    ):
        """! Set up the class of the fixed point finder
        @param problem must inherit pyoculus.problems.BaseProblem, the problem to solve
        @param params dict, the parameters for the solver
        @param integrator the integrator to use, must inherit \pyoculus.integrators.BaseIntegrator, if set to None by default using RKIntegrator
        @param integrator_params dict, the parmaters passed to the integrator

        <code> params['niter']=100 </code> -- the maximum number of Newton iterations

        <code> params['theta']=None </code>-- if we look for fixed point on some symmetry line
                        =None : theta is also a free variable to look for
                        =somenumber : only look for theta with this number

        <code> params['zeta']=0.0 </code>-- the toroidal plane we are after

        <code> params['nrestart']=1 </code>-- if search failed, the number of time to restart (randomly within the domain)
        """

        if "niter" not in params.keys():
            params["niter"] = 100

        if "theta" not in params.keys():
            params["theta"] = None

        if "zeta" not in params.keys():
            params["zeta"] = 0.0

        if "nrestart" not in params.keys():
            params["nrestart"] = 1

        # detect the type of the problem
        if isinstance(problem, ToroidalProblem):
            self._is_cylindrical_problem = False
            if "theta" not in params.keys():
                params["theta"] = None

            if params["theta"] is None:
                self.is_theta_fixed = False
            else:
                self.is_theta_fixed = True

        elif isinstance(problem, CylindricalProblem):
            self._is_cylindrical_problem = True
            if "Z" not in params.keys():
                params["Z"] = None

            if params["Z"] is None:
                self.is_Z_fixed = False
            else:
                self.is_Z_fixed = True

        else:
            raise TypeError(
                "problem should inherit either ToroidalProblem or CylindricalProblem"
            )
        
        if evolve_axis:
            integrator_params["ode"] = problem.f_tangent
        else:
            integrator_params["ode"] = problem.f_RZ_tangent

        super().__init__(
            problem=problem,
            params=params,
            integrator=integrator,
            integrator_params=integrator_params,
        )

        self.Nfp = problem.Nfp
        self.niter = params["niter"]
        self.nrestart = params["nrestart"]

    def compute(self, guess, pp, qq, sbegin=-1.0, send=1.0, tol=None, checkonly=True):
        """! Looks for the fixed point with rotation number pp/qq
        @param guess the initial guess, `[s, theta]`, if `params['theta'] == None`, `[s]`, if `params['theta'] ==` somevalue
        @param pp integer, the numerator (toroidal number) of the rotation number (iota = q^-1)
        @param qq integer, the denominator (poloidal number) of the rotation number (iota = q^-1)
        @param sbegin=-1.0 the allowed minimum s or R
        @param send=1.0    the allowed maximum s or R
        @param tol=self._integrator_params['rtol']*qq -- the tolerance of the fixed point
        @param checkonly=False, if set to True finds the fixed point in (R,Z) plane and then checks if the poloidal number is correct

        @returns rdata a class that contains the results that contains
        `rdata.x,rdata.y,rdata.z` -- the fixed points in xyz coordinates

        `rdata.s,rdata,theta,rdata,zeta` -- the fixed points in s,theta,zeta coordinates

        `rdata.jacobian` -- the Jacobian of the fixed point constructed by following the tangent map

        `rdata.GreenesResidue` -- the Greene's Residue of the fixed point

        `rdata.MeanResidue` -- the 'Average Residue' f as defined by Greene
        """

        if not isinstance(pp, int) or not isinstance(qq, int):
            raise ValueError("pp and qq should be integers")

        if tol is None:
            tol = self._integrator_params["rtol"] * qq

        if pp * qq >= 0:
            pp = int(np.abs(pp))
            qq = int(np.abs(qq))
        else:
            pp = -int(np.abs(pp))
            qq = int(np.abs(qq))
        # if np.gcd(pp, qq) != 1:

        self.pp = pp
        self.qq = qq
        self.dzeta = 2 * np.pi / self.Nfp

        # arrays that save the data
        self.s = np.zeros([qq + 1], dtype=np.float64)
        self.theta = np.zeros([qq + 1], dtype=np.float64)
        self.zeta = np.zeros([qq + 1], dtype=np.float64)
        self.x = np.zeros([qq + 1], dtype=np.float64)
        self.y = np.zeros([qq + 1], dtype=np.float64)
        self.z = np.zeros([qq + 1], dtype=np.float64)

        self.history = []

        # set up the guess
        if isinstance(guess, float):
            s_guess = guess
        else:
            guess = np.array(guess, dtype=np.float64)
            s_guess = guess[0]

        if not self._is_cylindrical_problem:
            if self._params["theta"] is None:
                theta_guess = guess[1]
            else:
                theta_guess = self._params["theta"]
        else:
            if self._params["Z"] is None:
                Z_guess = guess[1]
            else:
                Z_guess = self._params["Z"]

        # run the Newton's method
        for ii in range(self._params["nrestart"] + 1):
            try:  # run the solver, if failed, try a different random initial condition
                if self._is_cylindrical_problem:
                    if self.is_Z_fixed:
                        result = self._newton_method_3(
                            pp,
                            qq,
                            s_guess,
                            sbegin,
                            send,
                            Z_guess,
                            self._params["zeta"],
                            self.dzeta,
                            self.niter,
                            tol,
                        )
                    else:
                        result = self._newton_method_RZ(
                            pp,
                            qq,
                            s_guess,
                            sbegin,
                            send,
                            Z_guess,
                            self._params["zeta"],
                            self.dzeta,
                            self.niter,
                            tol,
                            checkonly
                        )
                else:
                    if self.is_theta_fixed:
                        result = self._newton_method_1(
                            pp,
                            qq,
                            s_guess,
                            sbegin,
                            send,
                            theta_guess,
                            self._params["zeta"],
                            self.dzeta,
                            self.niter,
                            tol,
                        )
                    else:
                        result = self._newton_method_2(
                            pp,
                            qq,
                            s_guess,
                            sbegin,
                            send,
                            theta_guess,
                            self._params["zeta"],
                            self.dzeta,
                            self.niter,
                            tol,
                        )
            except AssertionError as ae:
                if ae.args[0] == "Found fixed-point as not the right poloidal number (pp)":
                    rdata = FixedPoint.OutputData()
                    rdata.failed = ae
                    return rdata
                else:
                    result = None
            except:
                    result = None


            if result is not None:  # if it is successful:
                break
            else:  # not successful, change to a random initial condition
                print("Search failed: starting from a random initial guesss!")
                random_guess = np.random.rand(2)
                s_guess = sbegin + (send - sbegin) * random_guess[0]
                if self._is_cylindrical_problem:
                    if self._params["Z"] is None:
                        Z_guess = random_guess[1] * (send - sbegin)
                else:
                    if self._params["theta"] is None:
                        theta_guess = random_guess[1] * 2 * np.pi

        # now we go and get all the fixed points by iterating the map                
        if result is not None:
            t = self.zeta[0]
            dt = 2 * np.pi / self.Nfp

            if self._is_cylindrical_problem:
                self.x[0] = result[0]
                self.z[0] = result[1]
                self.zeta[0] = self._params["zeta"]

                R0 = self._problem._R0
                Z0 = self._problem._Z0
                theta0 = np.arctan2(result[1]-Z0, result[0]-R0)

                self.theta[0] = theta0

                ic = np.array([result[0], result[1], R0, Z0, theta0, 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
            else:
                self.s[0] = result[0]
                self.theta[0] = result[1]
                self.zeta[0] = self._params["zeta"]

                ic = np.array([result[0], result[1], 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
            self._integrator.set_initial_value(t, ic)

            # integrate to get a series of fixed points
            for jj in range(1, qq + 1):

                # run the integrator
                st = self._integrator.integrate(t + dt)

                # extract the result to s theta zeta
                if self._is_cylindrical_problem:
                    self.x[jj] = st[0]
                    self.z[jj] = st[1]
                    self.theta[jj] = st[4]
                else:
                    self.s[jj] = st[0]
                    self.theta[jj] = st[1]
                self.zeta[jj] = t + dt

                # advance in time
                t = t + dt

            # convert coordinates
            if not self._is_cylindrical_problem:
                for jj in range(0, qq + 1):
                    stz = np.array(
                        [self.s[jj], self.theta[jj], self.zeta[jj]], dtype=np.float64
                    )
                    xyz = self._problem.convert_coords(stz)
                    self.x[jj] = xyz[0]
                    self.y[jj] = xyz[1]
                    self.z[jj] = xyz[2]

            rdata = FixedPoint.OutputData()
            rdata.failed = None
            rdata.x = self.x.copy()
            rdata.y = self.y.copy()
            rdata.z = self.z.copy()
            rdata.s = self.s.copy()
            rdata.theta = self.theta.copy()
            rdata.zeta = self.zeta.copy()

            # the jacobian
            if self._is_cylindrical_problem:
                rdata.jacobian = np.array(
                    [[st[5], st[7]], [st[6], st[8]]], dtype=np.float64
                )
            else:
                rdata.jacobian = np.array(
                    [[st[2], st[4]], [st[3], st[5]]], dtype=np.float64
                )
            self.jacobian = rdata.jacobian
            
            # Greene's Residue
            rdata.GreenesResidue = 0.25 * (2.0 - np.trace(rdata.jacobian))
            rdata.MeanResidue = np.power(
                np.abs(rdata.GreenesResidue) / 0.25, 1 / float(qq)
            )
            self.GreenesResidue = rdata.GreenesResidue
            self.MeanResidue = rdata.MeanResidue

            # set the successful flag
            self.successful = True

        else:
            rdata = None
            print("Fixed point search unsuccessful for pp/qq=", pp, "/", qq)

        return rdata

    def compute_all_jacobians(self):
        """! Computes the fixed point evolution and founds its other apparences as well as computing
        the Jacobian and Greene's Residue for every apparition."""

        if not self.successful:
            raise Exception("A successful call of compute() is needed")
        
        # We iterate the map to get the fixed points and the Jacobian
        t = self.zeta[0]
        dt = 2 * np.pi / self.Nfp

        ic_list = []
        if self._is_cylindrical_problem:
            R0 = self._problem._R0
            Z0 = self._problem._Z0
            for r, z in zip(self.x[1:-2], self.z[1:-2]):
                theta0 = np.arctan2(z-Z0, r-R0)
                ic = np.array([r, z, R0, Z0, theta0, 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
                ic_list.append(ic)
        else:
            for s, theta in zip(self.s[1:-2], self.theta[1:-2]):
                ic = np.array([s, theta, 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
                ic_list.append(ic)

        self.all_jacobians = [self.jacobian]
        for ic in ic_list:
            self._integrator.set_initial_value(t, ic)
            for _ in range(1, self.qq + 1):
                st = self._integrator.integrate(t + dt)
                t = t + dt

            # the jacobian
            if self._is_cylindrical_problem:
                self.all_jacobians.append(np.array(
                    [[st[5], st[7]], [st[6], st[8]]], dtype=np.float64
                ))
            else:
                self.all_jacobians.append(np.array(
                    [[st[2], st[4]], [st[3], st[5]]], dtype=np.float64
                ))
        
        self.all_GreenesResidues = []
        self.all_MeanResidues = []
        for jac in self.all_jacobians:
            # Greene's Residue
            greensres = 0.25 * (2.0 - np.trace(jac))
            self.all_GreenesResidues.append(greensres)
            self.all_MeanResidues.append(np.power(
                np.abs(self.GreenesResidue) / 0.25, 1 / float(self.qq)
            ))

    def plot(
        self, plottype=None, xlabel=None, ylabel=None, xlim=None, ylim=None, **kwargs
    ):
        """! Generates the plot for fixed points
        @param plottype which variables to plot: 'RZ' or 'yx', by default using "poincare_plot_type" in problem
        @param xlabel,ylabel what to put for the xlabel and ylabel, by default using "poincare_plot_xlabel" in problem
        @param xlim, ylim the range of plotting, by default plotting the range of all data
        @param **kwargs passed to the plotting routine "plot"
        """
        import matplotlib.pyplot as plt

        if not self.successful:
            raise Exception("A successful call of compute() is needed")

        # default setting
        if plottype is None:
            plottype = self._problem.poincare_plot_type
        if xlabel is None:
            xlabel = self._problem.poincare_plot_xlabel
        if ylabel is None:
            ylabel = self._problem.poincare_plot_ylabel

        if plottype == "RZ":
            xdata = self.x
            ydata = self.z
        elif plottype == "yx":
            xdata = self.y
            ydata = self.x
        elif plottype == "st":
            xdata = np.mod(self.theta, 2 * np.pi)
            ydata = self.s
        else:
            raise ValueError("Choose the correct type for plottype")

        if plt.get_fignums():
            fig = plt.gcf()
            ax = plt.gca()
            newfig = False
        else:
            fig, ax = plt.subplots()
            newfig = True

        # set default plotting parameters
        # use x
        if kwargs.get("marker") is None:
            kwargs.update({"marker": "x"})
        # use gray color
        if kwargs.get("c") is None:
            kwargs.update({"c": "black"})

        xs = ax.plot(xdata, ydata, linestyle="None", **kwargs)

        if not newfig:
            if plottype == "RZ":
                plt.axis("equal")
            if plottype == "yx":
                pass

            plt.xlabel(xlabel, fontsize=20)
            plt.ylabel(ylabel, fontsize=20)
            plt.xticks(fontsize=16)
            plt.yticks(fontsize=16)

            if xlim is not None:
                plt.xlim(xlim)
            if ylim is not None:
                plt.ylim(ylim)

    def _newton_method_1(
        self, pp, qq, s_guess, sbegin, send, theta, zeta, dzeta, niter, tol
    ):
        """driver to run Newton's method for one variable s
        pp,qq -- integers, the numerator and denominator of the rotation number
        s_guess -- the guess of s
        sbegin -- the allowed minimum s
        send -- the allowed maximum s
        theta -- the theta value (fixed)
        zeta -- the toroidal plain to investigate
        dzeta -- period in zeta
        niter -- the maximum number of iterations
        tol -- the tolerance of finding a fixed point
        """

        s = s_guess

        # set up the initial condition
        ic = np.array([s, theta, 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
        self.history.append(ic[0:1].copy())

        t0 = zeta
        dt = dzeta

        succeeded = False

        for ii in range(niter):
            t = t0
            self._integrator.set_initial_value(t0, ic)

            for jj in range(qq):
                output = self._integrator.integrate(t + dt)
                t = t + dt

            dtheta = output[1] - theta - dzeta * pp
            jacobian = output[3]

            # if the resolution is good enough
            if abs(dtheta) < tol:
                succeeded = True
                break
            s_new = s - dtheta / jacobian
            s = s_new

            if s > send or s < sbegin:  # search failed, return None
                return None

            ic = np.array([s, theta, 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
            self.history.append(ic[0:1].copy())

        if succeeded:
            return np.array([s, theta, zeta], dtype=np.float64)
        else:
            return None

    def _newton_method_2(
        self, pp, qq, s_guess, sbegin, send, theta_guess, zeta, dzeta, niter, tol
    ):
        """driver to run Newton's method for two variable (s,theta)
        pp,qq -- integers, the numerator and denominator of the rotation number
        s_guess -- the guess of s
        sbegin -- the allowed minimum s
        send -- the allowed maximum s
        theta_guess -- the guess of theta
        zeta -- the toroidal plain to investigate
        dzeta -- period in zeta
        niter -- the maximum number of iterations
        tol -- the tolerance of finding a fixed point
        """

        self.successful = False

        s = s_guess
        theta = theta_guess

        # set up the initial condition
        ic = np.array([s, theta, 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
        self.history.append(ic[0:1].copy())

        t0 = zeta
        dt = dzeta

        succeeded = False

        st = np.array([s, theta], dtype=np.float64)

        for ii in range(niter):
            t = t0
            self._integrator.set_initial_value(t0, ic)
            for jj in range(qq):
                output = self._integrator.integrate(t + dt)
                t = t + dt

            dtheta = output[1] - theta - dzeta * pp
            ds = output[0] - s
            dst = np.array([ds, dtheta], dtype=np.float64)
            jacobian = np.array(
                [[output[2], output[4]], [output[3], output[5]]], dtype=np.float64
            )

            # if the resolution is good enough
            if np.sqrt(dtheta ** 2 + ds ** 2) < tol:
                succeeded = True
                break

            # Newton's step
            st_new = st - np.matmul(np.linalg.inv(jacobian - np.eye(2)), dst)
            s = st_new[0]
            theta = st_new[1]
            st = st_new

            if s > send or s < sbegin:  # search failed, return None
                return None

            ic = np.array([s, theta, 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
            self.history.append(ic[0:1].copy())

        if succeeded:
            self.successful = True
            return np.array([s, theta, zeta], dtype=np.float64)
        else:
            return None    

    def _newton_method_3(
        self, pp, qq, R_guess, Rbegin, Rend, Z, zeta, dzeta, niter, tol
    ):
        """driver to run Newton's method for one variable R, for cylindrical problem
        pp,qq -- integers, the numerator and denominator of the rotation number
        R_guess -- the guess of R
        Rbegin -- the allowed minimum R
        Rend -- the allowed maximum R
        Z -- the Z value (fixed)
        zeta -- the toroidal plain to investigate
        dzeta -- period in zeta
        niter -- the maximum number of iterations
        tol -- the tolerance of finding a fixed point
        """

        R = R_guess
        R0 = self._problem._R0
        Z0 = self._problem._Z0
        theta = np.arctan2(Z-Z0, R-R0)

        # set up the initial condition
        ic = np.array([R, Z, R0, Z0, theta, 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
        self.history.append(ic[0:1].copy())

        t0 = zeta
        dt = dzeta

        succeeded = False

        for ii in range(niter):
            t = t0
            self._integrator.set_initial_value(t0, ic)

            for jj in range(qq):
                output = self._integrator.integrate(t + dt)
                t = t + dt

            dtheta = output[4] - theta - dzeta * pp
            print(f"[R,Z] : {[output[0], output[1]]} - dtheta : {dtheta}")

            dR = output[5]
            dZ = output[6]
            
            deltaR = output[0] - R0
            deltaZ = output[1] - Z0

            jacobian = (deltaR * dZ - deltaZ * dR) / (deltaR**2 + deltaZ**2)

            # if the resolution is good enough
            if abs(dtheta) < tol:
                succeeded = True
                break
            R_new = R - dtheta / jacobian
            R = R_new
            print(f"R : {R}")
            theta = np.arctan2(Z-Z0, R-R0)

            if R > Rend or R < Rbegin:  # search failed, return None
                return None

            ic = np.array([R, Z, R0, Z0, theta, 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
            self.history.append(ic[0:1].copy())

        if succeeded:
            return np.array([R, Z, zeta], dtype=np.float64)
        else:
            return None
    
    def _newton_method_RZ(
        self, pp, qq, R_guess, Rbegin, Rend, Z_guess, zeta, dzeta, niter, tol, checkonly
    ):
        # Set up the initial guess
        RZ = np.array([R_guess, Z_guess], dtype=np.float64)

        # Set up the initial condition  
        RZ_Axis = np.array([self._problem._R0, self._problem._Z0], dtype=np.float64)
        rhotheta = np.array([np.linalg.norm(RZ-RZ_Axis), np.arctan2(RZ[1]-RZ_Axis[1], RZ[0]-RZ_Axis[0])], dtype=np.float64)
        
        ic = np.array([RZ[0], RZ[1], RZ_Axis[0], RZ_Axis[1], rhotheta[1], 1.0, 0.0, 0.0, 1.0], dtype=np.float64)
        
        self.history_Revolved = []
        self.history.append(ic[0:2].copy())
        
        t0 = zeta
        dt = dzeta

        succeeded = False

        for ii in range(niter):

            t = t0
            self._integrator.set_initial_value(t0, ic)

            for jj in range(qq):
                output = self._integrator.integrate(t + dt)
                t = t + dt

            RZ_evolved = np.array([output[0],output[1]])
            rhotheta_evolved = np.array([np.linalg.norm(RZ_evolved-RZ_Axis), 
                                         output[4] - dzeta * pp], dtype=np.float64)
            
            # Stop if the resolution is good enough
            condA = checkonly and np.linalg.norm(RZ_evolved-RZ) < tol
            condB = (not checkonly) and abs(rhotheta_evolved[1]-rhotheta[1]) < tol
            print(f"{ii} - [DeltaR, DeltaZ] : {RZ_evolved-RZ} - dtheta : {abs(rhotheta_evolved[1]-rhotheta[1])}")
            if condA or condB:
                succeeded = True
                break
            
            # dG switch to the convention of 
            # df = [[dG^R/dR, dG^r/dZ]
            #       [dG^Z/dR, df^Z/dZ]]
            dG = np.array([
                [output[5], output[7]],
                [output[6], output[8]]
            ], dtype=np.float64)

            if not checkonly:
                # dH = dH(G(R,Z))
                deltaRZ = RZ_evolved - RZ_Axis
                dH = np.array([
                    np.array([deltaRZ[0], deltaRZ[1]], dtype=np.float64) / np.sqrt(deltaRZ[0]**2 + deltaRZ[1]**2),
                    np.array([-deltaRZ[1], deltaRZ[0]], dtype=np.float64) / (deltaRZ[0]**2 + deltaRZ[1]**2)
                ], dtype=np.float64)

                # dP = dH(R,Z)
                deltaRZ = RZ - RZ_Axis
                dP = np.array([
                    np.array([deltaRZ[0], deltaRZ[1]], dtype=np.float64) / np.sqrt(deltaRZ[0]**2 + deltaRZ[1]**2),
                    np.array([-deltaRZ[1], deltaRZ[0]], dtype=np.float64) / (deltaRZ[0]**2 + deltaRZ[1]**2)
                ], dtype=np.float64)
                
                # Jacobian of the map F = H(G(R,Z)) - H(R,Z) 
                jacobian = dH @ dG - dP
                
                # Map F = H(G(R,Z)) - H(R,Z)
                F_evolved = rhotheta_evolved-rhotheta

            else:
                # Jacobian of the map F = G(R,Z) - (R,Z)
                jacobian = dG - np.eye(2)

                # Map F = G(R,Z) - (R,Z)
                F_evolved = RZ_evolved-RZ

            # Newton's step
            step = np.linalg.solve(jacobian, -1*F_evolved)
            RZ_new = RZ + step
            
            # Update the variables
            print(f"{ii} - [StepR, StepZ]: {RZ_new-RZ}")
            RZ = RZ_new
            rhotheta = np.array([np.linalg.norm(RZ-RZ_Axis), 
                                 np.arctan2(RZ[1]-RZ_Axis[1], RZ[0]-RZ_Axis[0])], dtype=np.float64)

            print(f"{ii+1} - RZ : {RZ} - rhotheta : {rhotheta}")
            # Check if the search is out of the provided R domain
            if RZ[0] > Rend or RZ[0] < Rbegin:
                return None
            
            ic = np.array([RZ[0], RZ[1], RZ_Axis[0], RZ_Axis[1], rhotheta[1], 1.0, 0.0, 0.0, 1.0], dtype=np.float64)

            self.history.append(ic[0:2].copy())
            self.history_Revolved.append(RZ_evolved)

        if succeeded:
            #assert abs(rhotheta_evolved[1]-rhotheta[1]) < 1e-3, "Found fixed-point as not the right poloidal number (pp)"
            return np.array([RZ[0], RZ[1], zeta], dtype=np.float64)
        else:
            return None
    
    def find_axis(
        self, R_guess, Rbegin, Rend, Z_guess, niter, tol
    ):
        if not isinstance(self._problem, CylindricalProblem):
            raise TypeError("problem should inherit CylindricalProblem to find an unknown axis")

        # Set up the initial guess
        RZ = np.array([R_guess, Z_guess], dtype=np.float64)
        
        ic = np.array([RZ[0], RZ[1], 1.0, 0.0, 0.0, 1.0], dtype=np.float64)

        self.history = []
        self.history.append(ic[0:2].copy())
        
        t0 = self._params["zeta"]
        dt = 2 * np.pi / self.Nfp

        succeeded = False

        for ii in range(niter):

            t = t0
            self._integrator.set_initial_value(t0, ic)
            
            # Integrate to the next periodic plane
            output = self._integrator.integrate(t + dt)
            t = t + dt

            RZ_evolved = np.array([output[0],output[1]])
            
            # Stop if the resolution is good enough
            print(f"{ii} - dr : {np.linalg.norm(RZ_evolved-RZ)}")
            if np.linalg.norm(RZ_evolved-RZ) < tol:
                succeeded = True
                break
            
            # dG switch to the convention of 
            # df = [[dG^R/dR, dG^r/dZ]
            #       [dG^Z/dR, df^Z/dZ]]
            dG = np.array([
                [output[2], output[4]],
                [output[3], output[5]]
            ], dtype=np.float64)

            # Jacobian of the map F = G(R,Z) - (R,Z)
            jacobian = dG - np.eye(2)

            # Map F = G(R,Z) - (R,Z)
            F_evolved = RZ_evolved-RZ

            # Newton's step
            step = np.linalg.solve(jacobian, -1*F_evolved)
            RZ_new = RZ + step
            
            # Update the variables
            RZ = RZ_new
           
            print(f"{ii+1} - RZ : {RZ}")
            # Check if the search is out of the provided R domain
            if RZ[0] > Rend or RZ[0] < Rbegin:
                return None
            
            ic = np.array([RZ[0], RZ[1], 1.0, 0.0, 0.0, 1.0], dtype=np.float64)

            self.history.append(ic[0:2].copy())

        if succeeded:
            return np.array([RZ[0], RZ[1], t0], dtype=np.float64)
        else:
            return None