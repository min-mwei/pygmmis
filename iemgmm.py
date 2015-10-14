#!/bin/env python

import numpy as np

def draw(amp, mean, covar, size=1, sel_callback=None, invert_callback=False):
    amp /= amp.sum()
    # draw indices for components given amplitudes
    K = amp.size
    D = mean.shape[1]
    ind = np.random.choice(K, size=size, p=amp)
    samples = np.empty((size, D))
    counter = 0
    if size > K:
        bc = np.bincount(ind)
        components = np.arange(ind.size)[bc > 0]
        for c in components:
            mask = ind == c
            s = mask.sum()
            samples[counter:counter+s] = np.random.multivariate_normal(mean[c], covar[c], size=s)
            counter += s
    else:
        for i in ind:
            samples[counter] = np.random.multivariate_normal(mean[i], covar[i], size=1)
            counter += 1

    # if subsample with selection is required
    if sel_callback is not None:
        sel_ = sel_callback(samples)
        if invert_callback:
            sel_ = np.invert(sel_)
        size_in = sel_.sum()
        if size_in != size:
            ssamples = draw(amp, mean, covar, size=size-size_in, sel_callback=sel_callback, invert_callback=invert_callback)
            samples = np.concatenate((samples[sel_], ssamples))
    return samples

def logsumLogL(ll):
    """Computes log of sum of likelihoods for GMM components.
    
    This method tries hard to avoid over- or underflow that may arise
    when computing exp(log(p(x | k)).
    
    See appendix A of Bovy, Hogg, Roweis (2009).
    
    Args:
    ll: (K, N) log-likelihoods from K calls to logL_K() with N coordinates
    
    Returns:
    (N, 1) of log of total likelihood
    
    """
    # typo in eq. 58: log(N) -> log(K)
    K = ll.shape[0]
    floatinfo = np.finfo('d')
    underflow = np.log(floatinfo.tiny) - ll.min(axis=0)
    overflow = np.log(floatinfo.max) - ll.max(axis=0) - np.log(K)
    c = np.where(underflow < overflow, underflow, overflow)
    return np.log(np.exp(ll + c).sum(axis=0)) - c

def E(data, amp, mean, covar):
    K = amp.size
    D = mean.shape[1]
    qij = np.empty((data.shape[0], K))
    for j in xrange(K):
        dx = data - mean[j]
        chi2 = np.einsum('...j,j...', dx, np.dot(np.linalg.inv(covar[j]), dx.T))
        qij[:,j] = np.log(amp[j]) - np.log((2*np.pi)**D * np.linalg.det(covar[j]))/2 - chi2/2
    for j in xrange(K):
        qij[:,j] -= logsumLogL(qij.T)
    return qij

def M(data, qij, amp, mean, covar, impute=0):
    K = amp.size
    D = mean.shape[1]
    N = data.shape[0] - impute
    qj = np.exp(logsumLogL(qij))
    if impute:
        qj_in = np.exp(logsumLogL(qij[:-impute]))
        qj_out = np.exp(logsumLogL(qij[-impute:]))
        covar_ = np.empty((D,D))
        
    for j in xrange(K):
        Q_i = np.exp(qij[:,j])
        amp[j] = qj[j]/(N+impute)
        
        # do covar first since we can do this without a copy of mean here
        if impute:
            covar_[:,:] = covar[j]
        covar[j] = 0
        for i in xrange(N):
            covar[j] += Q_i[i] * np.outer(data[i]-mean[j], (data[i]-mean[j]).T)
        if impute == 0:
            covar[j] /= qj[j]
        else:
            covar[j] /= qj_in[j]
            covar[j] += qj_out[j] / qj[j] * covar_
            
        # now update means
        for d in xrange(D):
            mean[j,d] = (data[:,d] * Q_i).sum()/qj[j]

def I(amp, mean, covar, impute=0, sel_callback=None):
    return draw(amp, mean, covar, size=impute, sel_callback=sel_callback, invert_callback=True)
    
def initialize(amp, mean, covar):
    K = amp.size
    D = mean.shape[1]

    # initialize GMM with equal weigths, random positions, fixed covariances
    amp[:] = 1./K
    mean[:,:] = np.random.random(size=(K, D))
    target_size = 0.1
    covar[:,:,:] = np.tile(target_size**2 * np.eye(D), (K,1,1))
            
def run_EM(data, amp, mean, covar, impute=0, sel_callback=None):
    initialize(amp, mean, covar)

    iter = 0
    while iter < 50: 
        try:
            if impute == 0 or iter < 25 or iter % 2 == 0:
                qij = E(data, amp, mean, covar)
                M(data, qij, amp, mean, covar)
            else:
                data_out = I(amp, mean, covar, impute=impute, sel_callback=sel_callback)
                data_ = np.concatenate((data, data_out), axis=0)
                
                qij = E(data_, amp, mean, covar)
                M(data_, qij, amp, mean, covar, impute=impute)
        except np.linalg.linalg.LinAlgError:
            iter = 0
            initialize(amp, mean, covar)
        iter += 1

def run_test(data, K=3, R=100, sel=None, sel_callback=None):
    D = data.shape[1]
    amp = None
    mean = None
    covar = None
    for r in range(R):
        print r
        amp_ = np.empty(K)
        mean_ = np.empty((K, D))
        covar_ = np.empty((K, D, D))
        if sel is None:
            run_EM(data, amp_, mean_, covar_)
        else:
            run_EM(data, amp_, mean_, covar_, impute=(sel==False).sum(), sel_callback=sel_callback)
        if amp is None:
            amp = amp_
            mean = mean_
            covar = covar_
        else:
            amp = np.concatenate((amp, amp_))
            mean = np.concatenate((mean, mean_), axis=0)
            covar = np.concatenate((covar, covar_), axis=0)
    amp /= amp.sum()
    return amp, mean, covar







