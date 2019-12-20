import numpy

from numba import njit


@njit(cache=True)
def sum_input_likelihoods(child_indexes, result, likelihoods):
    C = child_indexes.shape[0]
    for child in range(C):
        index = child_indexes[child]
        plhs = likelihoods[child]
        index_height = index.shape[0]
        result_width = result.shape[1]
        if child == 0:
            for parent_col in range(index_height):
                child_col = index[parent_col]
                for motif in range(result_width):
                    result[parent_col, motif] = plhs[child_col, motif]
        else:
            for parent_col in range(index_height):
                child_col = index[parent_col]
                for motif in range(result_width):
                    result[parent_col, motif] *= plhs[child_col, motif]
    return result


@njit(cache=True)
def get_total_log_likelihood_step1(input_likelihoods, mprobs):
    res = 0.0
    for i in range(len(mprobs)):
        res += input_likelihoods[i] * mprobs[i]
    return res


@njit(cache=True)
def get_log_sum_across_sites(lhs, counts):
    log_lhs = numpy.log(lhs)
    res = 0.0
    for i in range(len(counts)):
        res += log_lhs[i] * counts[i]
    return res
