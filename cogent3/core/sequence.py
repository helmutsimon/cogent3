#!/usr/bin/env python
"""Contains classes that represent biological sequence data. These
provide generic biological sequence manipulation functions, plus functions
that are critical for the EVOLVE calculations.

WARNING: Do not import sequence classes directly! It is expected that you will
access them through the moltype module. Sequence classes depend on information
from the MolType that is _only_ available after MolType has been imported.

Sequences are intended to be immutable. This is not enforced by the code for
performance reasons, but don't alter the MolType or the sequence data after
creation.
"""

from functools import total_ordering
from .annotation import Map, Feature, _Annotatable
from cogent3.util.transform import KeepChars, for_seq, per_shortest, \
    per_longest
from cogent3.util.misc import DistanceFromMatrix
from cogent3.core.genetic_code import DEFAULT as DEFAULT_GENETIC_CODE, \
    GeneticCodes
from cogent3.parse import gff
from cogent3.format.fasta import fasta_from_sequences
from cogent3.core.info import Info as InfoClass
from numpy import array, zeros, put, nonzero, take, ravel, compress, \
    logical_or, logical_not, arange
from numpy.random import permutation
from operator import eq, ne
from random import shuffle
import re
import warnings

__author__ = "Rob Knight, Gavin Huttley, and Peter Maxwell"
__copyright__ = "Copyright 2007-2012, The Cogent Project"
__credits__ = ["Rob Knight", "Peter Maxwell", "Gavin Huttley",
               "Matthew Wakefield", "Daniel McDonald"]
__license__ = "GPL"
__version__ = "1.5.3-dev"
__maintainer__ = "Rob Knight"
__email__ = "rob@spot.colorado.edu"
__status__ = "Production"

ARRAY_TYPE = type(array(1))

# standard distance functions: left  because generally useful
frac_same = for_seq(f=eq, aggregator=sum, normalizer=per_shortest)
frac_diff = for_seq(f=ne, aggregator=sum, normalizer=per_shortest)


@total_ordering
class SequenceI(object):
    """Abstract class containing Sequence interface.

    Specifies methods that Sequence delegates to its MolType, and methods for
    detecting gaps.
    """
    # String methods delegated to self._seq -- remember to override if self._seq
    # isn't a string in your base class, but it's probably better to make
    # self._seq a property that contains the string.
    LineWrap = None  # used for formatting FASTA strings

    def __str__(self):
        """__str__ returns self._seq unmodified."""
        return self._seq

    def to_fasta(self, make_seqlabel=None):
        """Return string of self in FASTA format, no trailing newline

        Arguments:
            - make_seqlabel: callback function that takes the seq object and
              returns a label str
        """
        return fasta_from_sequences([self], make_seqlabel=make_seqlabel,
                                    line_wrap=self.LineWrap)

    def translate(self, *args, **kwargs):
        """translate() delegates to self._seq."""
        return self._seq.translate(*args, **kwargs)

    def count(self, item):
        """count() delegates to self._seq."""
        return self._seq.count(item)

    def __lt__(self, other):
        """compares based on the sequence string."""
        return self._seq < str(other)

    def __eq__(self, other):
        """compares based on the sequence string."""
        return self._seq == str(other)

    def __ne__(self, other):
        """compares based on the sequence string."""
        return self._seq != str(other)

    def __hash__(self):
        """__hash__ behaves like the sequence string for dict lookup."""
        return hash(self._seq)

    def __contains__(self, other):
        """__contains__ checks whether other is in the sequence string."""
        return other in self._seq

    def shuffle(self):
        """returns a randomized copy of the Sequence object"""
        randomized_copy_list = list(self)
        shuffle(randomized_copy_list)
        return self.__class__(''.join(randomized_copy_list), Info=self.Info)

    def complement(self):
        """Returns complement of self, using data from MolType.

        Always tries to return same type as item: if item looks like a dict,
        will return list of keys.
        """
        return self.__class__(self.MolType.complement(self), Info=self.Info)

    def strip_degenerate(self):
        """Removes degenerate bases by stripping them out of the sequence."""
        return self.__class__(self.MolType.strip_degenerate(self), Info=self.Info)

    def strip_bad(self):
        """Removes any symbols not in the alphabet."""
        return self.__class__(self.MolType.strip_bad(self), Info=self.Info)

    def strip_bad_and_gaps(self):
        """Removes any symbols not in the alphabet, and any gaps."""
        return self.__class__(self.MolType.strip_bad_and_gaps(self), Info=self.Info)

    def rc(self):
        """Returns reverse complement of self w/ data from MolType.

        Always returns same type self.
        """
        return self.__class__(self.MolType.rc(self), Info=self.Info)

    def is_gapped(self):
        """Returns True if sequence contains gaps."""
        return self.MolType.is_gapped(self)

    def is_gap(self, char=None):
        """Returns True if char is a gap.

        If char is not supplied, tests whether self is gaps only.
        """
        if char is None:  # no char - so test if self is all gaps
            return len(self) == self.count_gaps()
        else:
            return self.MolType.is_gap(char)

    def is_degenerate(self):
        """Returns True if sequence contains degenerate characters."""
        return self.MolType.is_degenerate(self)

    def is_valid(self):
        """Returns True if sequence contains no items absent from alphabet."""
        return self.MolType.is_valid(self)

    def is_strict(self):
        """Returns True if sequence contains only monomers."""
        return self.MolType.is_strict(self)

    def first_gap(self):
        """Returns the index of the first gap in the sequence, or None."""
        return self.MolType.first_gap(self)

    def first_degenerate(self):
        """Returns the index of first degenerate symbol in sequence, or None."""
        return self.MolType.first_degenerate(self)

    def first_invalid(self):
        """Returns the index of first invalid symbol in sequence, or None."""
        return self.MolType.first_invalid(self)

    def first_non_strict(self):
        """Returns the index of first non-strict symbol in sequence, or None."""
        return self.MolType.first_non_strict(self)

    def disambiguate(self, method='strip'):
        """Returns a non-degenerate sequence from a degenerate one.

        method can be 'strip' (deletes any characters not in monomers or gaps)
        or 'random'(assigns the possibilities at random, using equal
        frequencies).
        """
        return self.__class__(self.MolType.disambiguate(self, method),
                              Info=self.Info)

    def degap(self):
        """Deletes all gap characters from sequence."""
        return self.__class__(self.MolType.degap(self), Info=self.Info)

    def gap_indices(self):
        """Returns list of indices of all gaps in the sequence, or []."""
        return self.MolType.gap_indices(self)

    def gap_vector(self):
        """Returns vector of True or False according to which pos are gaps."""
        return self.MolType.gap_vector(self)

    def gap_maps(self):
        """Returns dicts mapping between gapped and ungapped positions."""
        return self.MolType.gap_maps(self)

    def count_gaps(self):
        """Counts the gaps in the specified sequence."""
        return self.MolType.count_gaps(self)

    def count_degenerate(self):
        """Counts the degenerate bases in the specified sequence."""
        return self.MolType.count_degenerate(self)

    def possibilities(self):
        """Counts number of possible sequences matching the sequence.

        Uses self.Degenerates to decide how many possibilites there are at
        each position in the sequence.
        """
        return self.MolType.possibilities(self)

    def mw(self, method='random', delta=None):
        """Returns the molecular weight of (one strand of) the sequence.

        If the sequence is ambiguous, uses method (random or strip) to
        disambiguate the sequence.

        If delta is passed in, adds delta per strand (default is None, which
        uses the alphabet default. Typically, this adds 18 Da for terminal
        water. However, note that the default nucleic acid weight assumes
        5' monophosphate and 3' OH: pass in delta=18.0 if you want 5' OH as
        well.

        Note that this method only calculates the MW of the coding strand. If
        you want the MW of the reverse strand, add self.rc().mw(). DO NOT
        just multiply the MW by 2: the results may not be accurate due to
        strand bias, e.g. in mitochondrial genomes.
        """
        return self.MolType.mw(self, method, delta)

    def can_match(self, other):
        """Returns True if every pos in self could match same pos in other.

        Truncates at length of shorter sequence.
        Gaps are only allowed to match other gaps.
        """
        return self.MolType.can_match(self, other)

    def can_mismatch(self, other):
        """Returns True if any position in self could mismatch with other.

        Truncates at length of shorter sequence.
        Gaps are always counted as matches.
        """
        return self.MolType.can_mismatch(self, other)

    def must_match(self, other):
        """Returns True if all positions in self must match positions in other."""
        return self.MolType.must_match(self, other)

    def can_pair(self, other):
        """Returns True if self and other could pair.

        Pairing occurs in reverse order, i.e. last position of other with
        first position of self, etc.

        Truncates at length of shorter sequence.
        Gaps are only allowed to pair with other gaps, and are counted as 'weak'
        (same category as GU and degenerate pairs).

        NOTE: second must be able to be reverse
        """
        return self.MolType.can_pair(self, other)

    def can_mispair(self, other):
        """Returns True if any position in self could mispair with other.

        Pairing occurs in reverse order, i.e. last position of other with
        first position of self, etc.

        Truncates at length of shorter sequence.
        Gaps are always counted as possible mispairs, as are weak pairs like GU.
        """
        return self.MolType.can_mispair(self, other)

    def must_pair(self, other):
        """Returns True if all positions in self must pair with other.

        Pairing occurs in reverse order, i.e. last position of other with
        first position of self, etc.
        """
        return not self.MolType.can_mispair(self, other)

    def diff(self, other):
        """Returns number of differences between self and other.

        NOTE: truncates at the length of the shorter sequence. Case-sensitive.
        """
        return self.distance(other)

    def distance(self, other, function=None):
        """Returns distance between self and other using function(i,j).

        other must be a sequence.

        function should be a function that takes two items and returns a
        number. To turn a 2D matrix into a function, use
        cogent3.util.miscs.DistanceFromMatrix(matrix).

        NOTE: Truncates at the length of the shorter sequence.

        Note that the function acts on two _elements_ of the sequences, not
        the two sequences themselves (i.e. the behavior will be the same for
        every position in the sequences, such as identity scoring or a function
        derived from a distance matrix as suggested above). One limitation of
        this approach is that the distance function cannot use properties of
        the sequences themselves: for example, it cannot use the lengths of the
        sequences to normalize the scores as percent similarities or percent
        differences.

        If you want functions that act on the two sequences themselves, there
        is no particular advantage in making these functions methods of the
        first sequences by passing them in as parameters like the function
        in this method. It makes more sense to use them as standalone functions.
        The factory function cogent3.util.transform.for_seq is useful for
        converting per-element functions into per-sequence functions, since it
        takes as parameters a per-element scoring function, a score aggregation
        function, and a normalization function (which itself takes the two
        sequences as parameters), returning a single function that combines
        these functions and that acts on two complete sequences.
        """
        if function is None:
            # use identity scoring function
            function = lambda a, b: a != b
        distance = 0
        for first, second in zip(self, other):
            distance += function(first, second)
        return distance

    def matrix_distance(self, other, matrix):
        """Returns distance between self and other using a score matrix.

        WARNING: the matrix must explicitly contain scores for the case where
        a position is the same in self and other (e.g. for a distance matrix,
        an identity between U and U might have a score of 0). The reason the
        scores for the 'diagonals' need to be passed explicitly is that for
        some kinds of distance matrices, e.g. log-odds matrices, the 'diagonal'
        scores differ from each other. If these elements are missing, this
        function will raise a KeyError at the first position that the two
        sequences are identical.
        """
        return self.distance(other, DistanceFromMatrix(matrix))

    def frac_same(self, other):
        """Returns fraction of positions where self and other are the same.

        Truncates at length of shorter sequence.
        Note that frac_same and frac_diff are both 0 if one sequence is empty.
        """
        return frac_same(self, other)

    def frac_diff(self, other):
        """Returns fraction of positions where self and other differ.

        Truncates at length of shorter sequence.
        Note that frac_same and frac_diff are both 0 if one sequence is empty.
        """
        return frac_diff(self, other)

    def frac_same_gaps(self, other):
        """Returns fraction of positions where self and other share gap states.

        In other words, if self and other are both all gaps, or both all
        non-gaps, or both have gaps in the same places, frac_same_gaps will
        return 1.0. If self is all gaps and other has no gaps, frac_same_gaps
        will return 0.0. Returns 0 if one sequence is empty.

        Uses self's gap characters for both sequences.
        """
        if not self or not other:
            return 0.0

        is_gap = self.MolType.Gaps.__contains__
        return sum([is_gap(i) == is_gap(j) for i, j in zip(self, other)]) \
            / min(len(self), len(other))

    def frac_diff_gaps(self, other):
        """Returns frac. of positions where self and other's gap states differ.

        In other words, if self and other are both all gaps, or both all
        non-gaps, or both have gaps in the same places, frac_diff_gaps will
        return 0.0. If self is all gaps and other has no gaps, frac_diff_gaps
        will return 1.0.

        Returns 0 if one sequence is empty.

        Uses self's gap characters for both sequences.
        """
        if not self or not other:
            return 0.0
        return 1.0 - self.frac_same_gaps(other)

    def frac_same_non_gaps(self, other):
        """Returns fraction of non-gap positions where self matches other.

        Doesn't count any position where self or other has a gap.
        Truncates at the length of the shorter sequence.

        Returns 0 if one sequence is empty.
        """
        if not self or not other:
            return 0.0

        is_gap = self.MolType.Gaps.__contains__
        count = 0
        identities = 0
        for i, j in zip(self, other):
            if is_gap(i) or is_gap(j):
                continue
            count += 1
            if i == j:
                identities += 1

        if count:
            return identities / count
        else:  # there were no positions that weren't gaps
            return 0

    def frac_diff_non_gaps(self, other):
        """Returns fraction of non-gap positions where self differs from other.

        Doesn't count any position where self or other has a gap.
        Truncates at the length of the shorter sequence.

        Returns 0 if one sequence is empty. Note that this means that
        frac_diff_non_gaps is _not_ the same as 1 - frac_same_non_gaps, since both
        return 0 if one sequence is empty.
        """
        if not self or not other:
            return 0.0

        is_gap = self.MolType.Gaps.__contains__
        count = 0
        diffs = 0
        for i, j in zip(self, other):
            if is_gap(i) or is_gap(j):
                continue
            count += 1
            if i != j:
                diffs += 1

        if count:
            return diffs / count
        else:  # there were no positions that weren't gaps
            return 0

    def frac_similar(self, other, similar_pairs):
        """Returns fraction of positions where self[i] is similar to other[i].

        similar_pairs must be a dict such that d[(i,j)] exists if i and j are
        to be counted as similar. Use PairsFromGroups in cogent3.util.misc to
        construct such a dict from a list of lists of similar residues.

        Truncates at the length of the shorter sequence.

        Note: current implementation re-creates the distance function each
        time, so may be expensive compared to creating the distance function
        using for_seq separately.

        Returns 0 if one sequence is empty.
        """
        if not self or not other:
            return 0.0

        return for_seq(f=lambda x, y: (x, y) in similar_pairs,
                       normalizer=per_shortest)(self, other)

    def with_termini_unknown(self):
        """Returns copy of sequence with terminal gaps remapped as missing."""
        gaps = self.gap_vector()
        first_nongap = last_nongap = None
        for i, state in enumerate(gaps):
            if not state:
                if first_nongap is None:
                    first_nongap = i
                last_nongap = i
        missing = self.MolType.Missing
        if first_nongap is None:  # sequence was all gaps
            result = self.__class__(
                [missing for i in len(self)], Info=self.Info)
        else:
            prefix = missing * first_nongap
            mid = str(self[first_nongap:last_nongap + 1])
            suffix = missing * (len(self) - last_nongap - 1)
            result = self.__class__(prefix + mid + suffix, Info=self.Info)
        return result


@total_ordering
class Sequence(_Annotatable, SequenceI):
    """Holds the standard Sequence object. Immutable."""
    MolType = None  # connected to ACSII when moltype is imported

    def __init__(self, Seq='', Name=None, Info=None, check=True,
                 preserve_case=False, gaps_allowed=True, wildcards_allowed=True):
        """Initialize a sequence.

        Arguments:
            Seq: the raw sequence string, default is ''

            Name: the sequence name

            check: if True (the default), validates against the MolType
        """
        if Name is None and hasattr(Seq, 'Name'):
            Name = Seq.Name
        self.Name = Name
        orig_seq = Seq
        if isinstance(Seq, Sequence):
            Seq = Seq._seq
        elif isinstance(Seq, ModelSequence):
            Seq = str(Seq)
        elif type(Seq) is not str:
            try:
                Seq = ''.join(Seq)
            except TypeError:
                Seq = ''.join(map(str, Seq))
        Seq = self._seq_filter(Seq)
        if not preserve_case and not Seq.isupper():
            Seq = Seq.upper()
        self._seq = Seq

        if check:
            self.MolType.verify_sequence(self._seq, gaps_allowed,
                                        wildcards_allowed)

        if not isinstance(Info, InfoClass):
            try:
                Info = InfoClass(Info)
            except TypeError:
                Info = InfoClass()
        if hasattr(orig_seq, 'Info'):
            try:
                Info.update(orig_seq.Info)
            except:
                pass
        self.Info = Info

        if isinstance(orig_seq, _Annotatable):
            self.copy_annotations(orig_seq)

    def _seq_filter(self, seq):
        """Returns filtered seq; used to do DNA/RNA conversions."""
        return seq

    def get_colour_scheme(self, colours):
        return {}

    def get_color_scheme(self, colors):  # alias to support US spelling
        return self.get_colour_scheme(colours=colors)

    def copy_annotations(self, other):
        self.annotations = other.annotations[:]

    def annotate_from_gff(self, f):
        first_seqname = None
        for (seqname, source, feature, start, end, score, strand,
                frame, attributes, comments) in gff.GffParser(f):
            if first_seqname is None:
                first_seqname = seqname
            else:
                assert seqname == first_seqname, (seqname, first_seqname)
            feat_label = gff.parse_attributes(attributes)
            self.add_feature(feature, feat_label, [(start, end)])

    def with_masked_annotations(self, annot_types, mask_char=None, shadow=False):
        """returns a sequence with annot_types regions replaced by mask_char
        if shadow is False, otherwise all other regions are masked.

        Arguments:
            - annot_types: annotation type(s)
            - mask_char: must be a character valid for the seq MolType. The
              default value is the most ambiguous character, eg. '?' for DNA
            - shadow: whether to mask the annotated regions, or everything but
              the annotated regions"""
        if mask_char is None:
            ambigs = [(len(v), c)
                      for c, v in list(self.MolType.Ambiguities.items())]
            ambigs.sort()
            mask_char = ambigs[-1][1]
        assert mask_char in self.MolType, 'Invalid mask_char %s' % mask_char

        annotations = []
        annot_types = [annot_types, [annot_types]][
            isinstance(annot_types, str)]
        for annot_type in annot_types:
            annotations += self.get_annotations_matching(annot_type)

        region = self.getRegionCoveringAll(annotations)
        if shadow:
            region = region.getShadow()

        i = 0
        segments = []
        for b, e in region.getCoordinates():
            segments.append(self._seq[i:b])
            segments.append(mask_char * (e - b))
            i = e
        segments.append(self._seq[i:])

        new = self.__class__(''.join(segments), Name=self.Name, check=False,
                             Info=self.Info)
        new.annotations = self.annotations[:]
        return new

    def gapped_by_map_segment_iter(self, map, allow_gaps=True, recode_gaps=False):
        for span in map.spans:
            if span.lost:
                if allow_gaps:
                    unknown = span.terminal or recode_gaps
                    seg = "-?"[unknown] * span.length
                else:
                    raise ValueError('Gap(s) in map %s' % map)
            else:
                seg = self._seq[span.Start:span.End]
                if span.Reverse:
                    complement = self.MolType.complement
                    seg = [complement(base) for base in seg[::-1]]
                    seg = ''.join(seg)
            yield seg

    def gapped_by_map_motif_iter(self, map):
        for segment in self.gapped_by_map_segment_iter(map):
            for motif in segment:
                yield motif

    def gapped_by_map(self, map, recode_gaps=False):
        segments = self.gapped_by_map_segment_iter(map, True, recode_gaps)
        new = self.__class__(''.join(segments),
                             Name=self.Name, check=False, Info=self.Info)
        annots = self._slicedAnnotations(new, map)
        new.annotations = annots
        return new

    def _mapped(self, map):
        # Called by generic __getitem__
        segments = self.gapped_by_map_segment_iter(map, allow_gaps=False)
        new = self.__class__(''.join(segments), self.Name, Info=self.Info)
        return new

    def __add__(self, other):
        """Adds two sequences (other can be a string as well)."""
        if hasattr(other, 'MolType'):
            if self.MolType != other.MolType:
                raise ValueError("MolTypes don't match: (%s,%s)" %
                                 (self.MolType, other.MolType))
            other_seq = other._seq
        else:
            other_seq = other
        new_seq = self.__class__(self._seq + other_seq)
        # Annotations which extend past the right end of the left sequence
        # or past the left end of the right sequence are dropped because
        # otherwise they will annotate the wrong part of the constructed
        # sequence.
        left = [a for a in self._shiftedAnnotations(new_seq, 0)
                if a.map.End <= len(self)]
        if hasattr(other, '_shiftedAnnotations'):
            right = [a for a in other._shiftedAnnotations(new_seq, len(self))
                     if a.map.Start >= len(self)]
            new_seq.annotations = left + right
        else:
            new_seq.annotations = left
        return new_seq

    def __repr__(self):
        myclass = '%s' % self.__class__.__name__
        myclass = myclass.split('.')[-1]
        if len(self) > 10:
            seq = str(self._seq[:7]) + '... %s' % len(self)
        else:
            seq = str(self._seq)
        return "%s(%s)" % (myclass, seq)

    def get_tracks(self, policy):
        return policy.tracksForSequence(self)

    def get_name(self):
        """Return the sequence name -- should just use Name instead."""

        return self.Name

    def __len__(self):
        return len(self._seq)

    def __iter__(self):
        return iter(self._seq)

    def gettype(self):
        """Return the sequence type."""

        return self.MolType.label

    def resolveambiguities(self):
        """Returns a list of tuples of strings."""
        ambigs = self.MolType.resolveAmbiguity
        return [ambigs(motif) for motif in self._seq]

    def sliding_windows(self, window, step, start=None, end=None):
        """Generator function that yield new sequence objects
        of a given length at a given interval.
        Arguments:
            - window: The length of the returned sequence
            - step: The interval between the start of the returned
              sequence objects
            - start: first window start position
            - end: last window start position
        """
        start = [start, 0][start is None]
        end = [end, len(self) - window + 1][end is None]
        end = min(len(self) - window + 1, end)
        if start < end and len(self) - end >= window - 1:
            for pos in range(start, end, step):
                yield self[pos:pos + window]

    def get_in_motif_size(self, motif_length=1, log_warnings=True):
        """returns sequence as list of non-overlapping motifs

        Arguments:
            - motif_length: length of the motifs
            - log_warnings: whether to notify of an incomplete terminal motif"""
        seq = self._seq
        if motif_length == 1:
            return seq
        else:
            length = len(seq)
            remainder = length % motif_length
            if remainder and log_warnings:
                warnings.warn('Dropped remainder "%s" from end of sequence' %
                              seq[-remainder:])
            return [seq[i:i + motif_length]
                    for i in range(0, length - remainder, motif_length)]

    def parse_out_gaps(self):
        gapless = []
        segments = []
        nongap = re.compile('([^%s]+)' % re.escape("-"))
        for match in nongap.finditer(self._seq):
            segments.append(match.span())
            gapless.append(match.group())
        map = Map(segments, parent_length=len(self)).inverse()
        seq = self.__class__(
            ''.join(gapless),
            Name=self.get_name(), Info=self.Info)
        if self.annotations:
            seq.annotations = [a.remapped_to(seq, map)
                               for a in self.annotations]
        return (map, seq)


class ProteinSequence(Sequence):
    """Holds the standard Protein sequence. MolType set in moltype module."""
    pass


class ProteinWithStopSequence(Sequence):
    """Holds the standard Protein sequence, allows for stop codon

    MolType set in moltype module
    """
    pass


class NucleicAcidSequence(Sequence):
    """Base class for DNA and RNA sequences. Abstract."""
    PROTEIN = None  # will set in moltype
    CodonAlphabet = None  # will set in moltype

    def reversecomplement(self):
        """Converts a nucleic acid sequence to its reverse complement.
        Synonymn for rc."""
        return self.rc()

    def rc(self):
        """Converts a nucleic acid sequence to its reverse complement."""
        complement = self.MolType.rc(self)
        rc = self.__class__(complement, Name=self.Name, Info=self.Info)
        self._annotations_nucleic_reversed_on(rc)
        return rc

    def _gc_from_arg(self, gc):
        # codon_alphabet is being deprecated in favor of genetic codes.
        if gc is None:
            gc = DEFAULT_GENETIC_CODE
        elif isinstance(gc, (int, str)):
            gc = GeneticCodes[gc]
        return gc

    def has_terminal_stop(self, gc=None, allow_partial=False):
        """Return True if the sequence has a terminal stop codon.

        Arguments:
            - gc: genetic code object
            - allow_partial: if True and the sequence length is not dividisble
              by 3, ignores the 3' terminal incomplete codon
        """
        gc = self._gc_from_arg(gc)
        codons = self._seq
        divisible_by_3 = len(codons) % 3 == 0

        if not allow_partial and not divisible_by_3:
            raise ValueError("seq length not divisible by 3")

        if not divisible_by_3:
            return False

        return codons and gc.isStop(codons[-3:])

    def without_terminal_stop_sodon(self, gc=None, allow_partial=False):
        """Removes a terminal stop codon from the sequence

        Arguments:
            - gc: genetic code object
            - allow_partial: if True and the sequence length is not divisible
              by 3, ignores the 3' terminal incomplete codon
        """
        gc = self._gc_from_arg(gc)
        codons = self._seq
        divisible_by_3 = len(codons) % 3 == 0

        if not allow_partial and not divisible_by_3:
            raise ValueError("seq length not divisible by 3")

        if divisible_by_3 and codons and gc.isStop(codons[-3:]):
            codons = codons[:-3]

        return self.__class__(codons, Name=self.Name, Info=self.Info)

    def get_translation(self, gc=None):
        gc = self._gc_from_arg(gc)
        codon_alphabet = self.CodonAlphabet(gc).withGapMotif()
        # translate the codons
        translation = []
        for posn in range(0, len(self._seq) - 2, 3):
            orig_codon = self._seq[posn:posn + 3]
            resolved = codon_alphabet.resolveAmbiguity(orig_codon)
            trans = []
            for codon in resolved:
                if codon == '---':
                    aa = '-'
                else:
                    assert '-' not in codon
                    aa = gc[codon]
                    if aa == '*':
                        continue
                trans.append(aa)
            if not trans:
                raise ValueError(orig_codon)
            aa = self.PROTEIN.what_ambiguity(trans)
            translation.append(aa)

        translation = self.PROTEIN.make_sequence(
            Seq=''.join(translation), Name=self.Name)

        return translation

    def get_orf_positions(self, gc=None, atg=False):
        gc = self._gc_from_arg(gc)
        orfs = []
        start = None
        protein = self.get_translation(gc=gc)
        for (posn, aa) in enumerate(protein):
            posn *= 3
            if aa == '*':
                if start is not None:
                    orfs.append((start, posn))
                start = None
            else:
                if start is None:
                    if (not atg) or gc.isStart(self[posn:posn + 3]):
                        start = posn
        if start is not None:
            orfs.append((start, posn + 3))
        return orfs

    def to_rna(self):
        """Returns copy of self as RNA."""
        return RnaSequence(self)

    def to_dna(self):
        """Returns copy of self as DNA."""
        return DnaSequence(self)


class DnaSequence(NucleicAcidSequence):

    def get_colour_scheme(self, colours):
        return {
            'A': colours.black,
            'T': colours.red,
            'C': colours.blue,
            'G': colours.green,
        }

    def _seq_filter(self, seq):
        """Converts U to T."""
        return seq.replace('u', 't').replace('U', 'T')


class RnaSequence(NucleicAcidSequence):

    def get_colour_scheme(self, colours):
        return {
            'A': colours.black,
            'U': colours.red,
            'C': colours.blue,
            'G': colours.green,
        }

    def _seq_filter(self, seq):
        """Converts T to U."""
        return seq.replace('t', 'u').replace('T', 'U')


class ABSequence(Sequence):
    """Used for two-state modeling; MolType set in moltypes."""
    pass


class ByteSequence(Sequence):
    """Used for storing arbitrary bytes."""

    def __init__(self, Seq='', Name=None, Info=None, check=False,
                 preserve_case=True):
        return super(ByteSequence, self).__init__(Seq, Name=Name, Info=Info,
                                                  check=check, preserve_case=preserve_case)


@total_ordering
class ModelSequenceBase(object):
    """Holds the information for a non-degenerate sequence. Mutable.

    A ModelSequence is an array of indices of symbols, where those symbols are
    defined by an Alphabet. This representation of Sequence is convenient for
    counting symbol frequencies or tuple frequencies, remapping data (e.g. for
    reverse-complement), looking up model parameters, etc. Its main drawback is
    that the sequences can no longer be treated as strings, and conversion
    to/from strings can be fairly time-consuming. Also, any symbol not in the
    Alphabet cannot be represented at all.

    A sequence can have a Name, which will be used for output in formats
    such as FASTA.

    A sequence Class has an alphabet (which can be overridden in instances
    where necessary), a delimiter used for string conversions, a LineWrap
    for wrapping characters into lines for e.g. FASTA output.

    Note that a ModelSequence _must_ have an Alphabet, not a MolType,
    because it is often important to store just a subset of the possible
    characters (e.g. the non-degenerate bases) for modeling purposes.
    """
    Alphabet = None  # REPLACE IN SUBCLASSES
    MolType = None  # REPLACE IN SUBCLASSES
    Delimiter = ''  # Used for string conversions
    LineWrap = 80  # Wrap sequences at 80 characters by default.

    def __init__(self, data='', Alphabet=None, Name=None, Info=None,
                 check='ignored'):
        """Initializes sequence from data and alphabet.

        WARNING: Does not validate the data or alphabet for compatibility.
        This is for speed. Use is_valid() to check whether the data
        is consistent with the alphabet.

        WARNING: If data has name and/or Info, gets ref to same object rather
        than copying in each case.
        """
        if Name is None and hasattr(data, 'Name'):
            Name = data.Name
        if Info is None and hasattr(data, 'Info'):
            Info = data.Info
        # set the label
        self.Name = Name
        # override the class alphabet if supplied
        if Alphabet is not None:
            self.Alphabet = Alphabet
        # if we haven't already set self._data (e.g. in a subclass __init__),
        # guess the data type and set it here
        if not hasattr(self, '_data'):
            # if data is a sequence, copy its data and alphabet
            if isinstance(data, ModelSequence):
                self._data = data._data
                self.Alphabet = data.Alphabet
            # if it's an array
            elif type(data) == ARRAY_TYPE:
                self._data = data
            else:  # may be set in subclass init
                self._from_sequence(data)

        self.MolType = self.Alphabet.MolType
        self.Info = Info

    def __getitem__(self, *args):
        """__getitem__ returns char or slice, as same class."""
        if len(args) == 1 and not isinstance(args[0], slice):
            result = array([self._data[args[0]]])
        else:
            result = self._data.__getitem__(*args)
        return self.__class__(result)

    def __lt__(self, other):
        """compares based on string"""
        return str(self) < other

    def __eq__(self, other):
        """compares based on string"""
        return str(self) == other

    def _from_sequence(self, data):
        """Fills self using the values in data, via the Alphabet."""
        if self.Alphabet:
            indices = self.Alphabet.to_indices(data)
            self._data = array(indices, self.Alphabet.ArrayType)
        else:
            self._data = array(data)

    def __str__(self):
        """Uses alphabet to convert self to string, using delimiter."""
        if hasattr(self.Alphabet, 'to_string'):
            return self.Alphabet.to_string(self._data)
        else:
            return self.Delimiter.join(map(str,
                                           self.Alphabet.from_indices(self._data)))

    def __len__(self):
        """Returns length of data."""
        return len(self._data)

    def to_fasta(self, make_seqlabel=None):
        """Return string of self in FASTA format, no trailing newline

        Arguments:
            - make_seqlabel: callback function that takes the seq object and
              returns a label str
        """
        return fasta_from_sequences([self], make_seqlabel=make_seqlabel,
                                    line_wrap=self.LineWrap)

    def to_phylip(self, name_len=28, label_len=30):
        """Return string of self in one line for PHYLIP, no newline.

        Default: max name length is 28, label length is 30.
        """
        return str(self.Name)[:name_len].ljust(label_len) + str(self)

    def is_valid(self):
        """Checks that no items in self are out of the Alphabet range."""
        return self._data == self._data.clip(m, 0, len(self.Alphabet) - 1)

    def to_k_words(self, k, overlapping=True):
        """Turns sequence into sequence of its k-words.

        Just returns array, not Sequence object."""
        alpha_len = len(self.Alphabet)
        seq = self._data
        seq_len = len(seq)
        if overlapping:
            num_words = seq_len - k + 1
        else:
            num_words, remainder = divmod(seq_len, k)
            last_index = num_words * k
        result = zeros(num_words)
        for i in range(k):
            if overlapping:
                curr_slice = seq[i:i + num_words]
            else:
                curr_slice = seq[i:last_index + i:k]
            result *= alpha_len
            result += curr_slice
        return result

    def __iter__(self):
        """iter returns characters of self, rather than slices."""
        if hasattr(self.Alphabet, 'to_string'):
            return iter(self.Alphabet.to_string(self._data))
        else:
            return iter(self.Alpabet.from_indices(self._data))

    def tostring(self):
        """tostring delegates to self._data."""
        return self._data.tostring()

    def gaps(self):
        """Returns array containing 1 where self has gaps, 0 elsewhere.

        WARNING: Only checks for standard gap character (for speed), and
        does not check for ambiguous gaps, etc.
        """
        return self._data == self.Alphabet.GapIndex

    def nongaps(self):
        """Returns array contining 0 where self has gaps, 1 elsewhere.

        WARNING: Only checks for standard gap character (for speed), and
        does not check for ambiguous gaps, etc.
        """
        return self._data != self.Alphabet.GapIndex

    def regap(self, other, strip_existing_gaps=False):
        """Inserts elements of self into gaps specified by other.

        WARNING: Only checks for standard gap character (for speed), and
        does not check for ambiguous gaps, etc.
        """
        if strip_existing_gaps:
            s = self.degap()
        else:
            s = self
        c = self.__class__
        a = self.Alphabet.Gapped
        result = zeros(len(other), a.ArrayType) + a.GapIndex
        put(result, nonzero(other.nongaps()), s._data)
        return c(result)

    def degap(self):
        """Returns ungapped copy of self, not changing alphabet."""
        if not hasattr(self.Alphabet, 'Gap') or self.Alphabet.Gap is None:
            return self.copy()
        d = take(self._data, nonzero(logical_not(self.gap_array()))[0])
        return self.__class__(d, Alphabet=self.Alphabet, Name=self.Name,
                              Info=self.Info)

    def copy(self):
        """Returns copy of self, always separate object."""
        return self.__class__(self._data.copy(), Alphabet=self.Alphabet,
                              Name=self.Name, Info=self.Info)

    def __contains__(self, item):
        """Returns true if item in self (converts to strings)."""
        return item in str(self)

    def disambiguate(self, *args, **kwargs):
        """Disambiguates self using strings/moltype. Should recode if demand."""
        return self.__class__(self.MolType.disambiguate(str(self),
                                                        *args, **kwargs))

    def distance(self, other, function=None, use_indices=False):
        """Returns distance between self and other using function(i,j).

        other must be a sequence.

        function should be a function that takes two items and returns a
        number. To turn a 2D matrix into a function, use
        cogent3.util.miscs.DistanceFromMatrix(matrix).

        use_indices: if False, maps the indices onto items (e.g. assumes
        function relates the characters). If True, uses the indices directly.

        NOTE: Truncates at the length of the shorter sequence.

        Note that the function acts on two _elements_ of the sequences, not
        the two sequences themselves (i.e. the behavior will be the same for
        every position in the sequences, such as identity scoring or a function
        derived from a distance matrix as suggested above). One limitation of
        this approach is that the distance function cannot use properties of
        the sequences themselves: for example, it cannot use the lengths of the
        sequences to normalize the scores as percent similarities or percent
        differences.

        If you want functions that act on the two sequences themselves, there
        is no particular advantage in making these functions methods of the
        first sequences by passing them in as parameters like the function
        in this method. It makes more sense to use them as standalone functions.
        The factory function cogent3.util.transform.for_seq is useful for
        converting per-element functions into per-sequence functions, since it
        takes as parameters a per-element scoring function, a score aggregation
        function, and a normalization function (which itself takes the two
        sequences as parameters), returning a single function that combines
        these functions and that acts on two complete sequences.
        """
        if function is None:
            # use identity scoring
            shortest = min(len(self), len(other))
            if not hasattr(other, '_data'):
                other = self.__class__(other)
            distance = (self._data[:shortest] != other._data[:shortest]).sum()
        else:
            distance = 0
            if use_indices:
                self_seq = self._data
                if hasattr(other, '_data'):
                    other_seq = other._data
            else:
                self_seq = self.Alphabet.from_indices(self._data)
                if hasattr(other, '_data'):
                    other_seq = other.Alphabet.from_indices(other._data)
                else:
                    other_seq = other
            for first, second in zip(self_seq, other_seq):
                distance += function(first, second)
        return distance

    def matrix_distance(self, other, matrix, use_indices=False):
        """Returns distance between self and other using a score matrix.

        if use_indices is True (default is False), assumes that matrix is
        an array using the same indices that self uses.

        WARNING: the matrix must explicitly contain scores for the case where
        a position is the same in self and other (e.g. for a distance matrix,
        an identity between U and U might have a score of 0). The reason the
        scores for the 'diagonals' need to be passed explicitly is that for
        some kinds of distance matrices, e.g. log-odds matrices, the 'diagonal'
        scores differ from each other. If these elements are missing, this
        function will raise a KeyError at the first position that the two
        sequences are identical.
        """
        return self.distance(other, DistanceFromMatrix(matrix))

    def shuffle(self):
        """Returns shuffled copy of self"""
        return self.__class__(permutation(self._data), Info=self.Info)

    def gap_array(self):
        """Returns array of 0/1 indicating whether each position is a gap."""
        gap_indices = []
        a = self.Alphabet
        for c in self.MolType.Gaps:
            if c in a:
                gap_indices.append(a.index(c))
        gap_vector = None
        for i in gap_indices:
            if gap_vector is None:
                gap_vector = self._data == i
            else:
                gap_vector = logical_or(gap_vector, self._data == i)
        return gap_vector

    def gap_indices(self):
        """Returns list of gap indices."""
        return list(self.gap_array().nonzero()[0])

    def frac_same_gaps(self, other):
        """Returns fraction of positions where gaps match other's gaps.
        """
        if not other:
            return 0
        self_gaps = self.gap_array()
        if hasattr(other, 'gap_array'):
            other_gaps = other.gap_array()
        elif hasattr(other, 'gap_vector'):
            other_gaps = array(other.gap_vector())
        else:
            other_gaps = array(self.MolType.gap_vector(other))
        min_len = min(len(self), len(other))
        self_gaps, other_gaps = self_gaps[:min_len], other_gaps[:min_len]
        return (self_gaps == other_gaps).sum() / float(min_len)


class ModelSequence(ModelSequenceBase, SequenceI):
    """ModelSequence provides an array-based implementation of Sequence.

    Use ModelSequenceBase if you need a stripped-down, fast implementation.
    ModelSequence implements everything that SequenceI implements.

    See docstrings for ModelSequenceBase and SequenceI for information about
    these respective classes.
    """

    def strip_bad(self):
        """Returns copy of self with bad chars excised"""
        valid_indices = self._data < len(self.Alphabet)
        result = compress(valid_indices, self._data)
        return self.__class__(result, Info=self.Info)

    def strip_bad_and_gaps(self):
        """Returns copy of self with bad chars and gaps excised."""
        gap_indices = list(map(self.Alphabet.index, self.MolType.Gaps))
        valid_indices = self._data < len(self.Alphabet)
        for i in gap_indices:
            valid_indices[self._data == i] = False
        result = compress(valid_indices, self._data)
        return self.__class__(result, Info=self.Info)

    def strip_degenerate(self):
        """Returns copy of self without degenerate symbols.

        NOTE: goes via string intermediate because some of the algorithms
        for resolving degenerates are complex. This could be optimized if
        speed becomes critical.
        """
        return self.__class__(self.MolType.strip_degenerate(str(self)),
                              Info=self.Info)

    def count_gaps(self):
        """Returns count of gaps in self."""
        return self.gap_array().sum()

    def gap_vector(self):
        """Returns list of bool containing whether each pos is a gap."""
        return list(map(bool, self.gap_array()))

    def gap_maps(self):
        """Returns dicts mapping gapped/ungapped positions."""
        nongaps = logical_not(self.gap_array())
        indices = arange(len(self)).compress(nongaps)
        new_indices = arange(len(indices))
        return dict(list(zip(new_indices, indices))), dict(list(zip(indices, new_indices)))

    def first_gap(self):
        """Returns position of first gap, or None."""
        a = self.gap_indices()
        try:
            return a[0]
        except IndexError:
            return None

    def is_gapped(self):
        """Returns True of sequence contains gaps."""
        return len(self.gap_indices())

    def mw(self, *args, **kwargs):
        """Returns molecular weight.

        Works via string intermediate: could optimize using array of MW if
        speed becomes important.
        """
        return self.MolType.mw(str(self), *args, **kwargs)

    def frac_similar(self, other, similar_pairs):
        """Returns fraction of positions where self[i] is similar to other[i].

        similar_pairs must be a dict such that d[(i,j)] exists if i and j are
        to be counted as similar. Use PairsFromGroups in cogent3.util.misc to
        construct such a dict from a list of lists of similar residues.

        Truncates at the length of the shorter sequence.

        Note: current implementation re-creates the distance function each
        time, so may be expensive compared to creating the distance function
        using for_seq separately.

        Returns 0 if one sequence is empty.

        NOTE: goes via string intermediate, could optimize using array if
        speed becomes important. Note that form of similar_pairs input would
        also have to change.
        """
        if not self or not other:
            return 0.0

        return for_seq(f=lambda x, y: (x, y) in similar_pairs,
                       normalizer=per_shortest)(str(self), str(other))


class ModelNucleicAcidSequence(ModelSequence):
    """Abstract class defining ops for codons, translation, etc."""

    def to_codons(self):
        """Returns copy of self in codon alphabet. Assumes ungapped."""
        alpha_len = len(self.Alphabet)
        return ModelCodonSequence(alpha_len * (
            alpha_len * self._data[::3] + self._data[1::3]) + self._data[2::3],
            Name=self.Name, Alphabet=self.Alphabet.Triples)

    def complement(self):
        """Returns complement of sequence"""
        return self.__class__(self.Alphabet._complement_array.take(self._data),
                              Info=self.Info)

    def rc(self):
        """Returns reverse-complement of sequence"""
        comp = self.Alphabet._complement_array.take(self._data)
        return self.__class__(comp[::-1], Info=self.Info)

    def to_rna(self):
        """Returns self as RNA"""
        return ModelRnaSequence(self._data)

    def to_dna(self):
        """Returns self as DNA"""
        return ModelDnaSequence(self._data)


class ModelRnaSequence(ModelNucleicAcidSequence):
    MolType = None  # set to RNA in moltype.py
    Alphabet = None  # set to RNA.Alphabets.DegenGapped in moltype.py

    def __init__(self, data='', *args, **kwargs):
        """Returns new ModelRnaSequence, converting T -> U"""
        if hasattr(data, 'upper'):
            data = data.upper().replace('T', 'U')
        return super(ModelNucleicAcidSequence, self).__init__(data,
                                                              *args, **kwargs)


class ModelDnaSequence(ModelNucleicAcidSequence):
    MolType = None  # set to DNA in moltype.py
    Alphabet = None  # set to DNA.Alphabets.DegenGapped in moltype.py

    def __init__(self, data='', *args, **kwargs):
        """Returns new ModelRnaSequence, converting U -> T"""
        if hasattr(data, 'upper'):
            data = data.upper().replace('U', 'T')
        return super(ModelNucleicAcidSequence, self).__init__(data,
                                                              *args, **kwargs)


class ModelCodonSequence(ModelSequence):
    """Abstract base class for codon sequences, incl. string conversion."""
    SequenceClass = ModelNucleicAcidSequence

    def __str__(self):
        """Joins triplets together as string."""
        return self.Delimiter.join(map(''.join,
                                       self.Alphabet.from_indices(self._data)))

    def _from_string(self, s):
        """Reads from a raw string, rather than a DnaSequence."""
        s = s.upper().replace('U', 'T')  # convert to uppercase DNA
        d = self.SequenceClass(s,
                               Alphabet=self.Alphabet.SubEnumerations[0])
        self._data = d.to_codons()._data

    def __init__(self, data='', Alphabet=None, Name=None, Info=None):
        """Override __init__ to handle init from string."""
        if isinstance(data, str):
            self._from_string(data)
        ModelSequence.__init__(self, data, Alphabet, Name, Info=Info)

    def to_codons(self):
        """Converts self to codons -- in practice, just returns self.

        Supports interface of other NucleicAcidSequences."""
        return self

    def to_dna(self):
        """Returns a ModelDnaSequence from the data in self"""
        unpacked = self.Alphabet.unpack_arrays(self._data)
        result = zeros((len(self._data), 3))
        for i, v in enumerate(unpacked):
            result[:, i] = v
        return ModelDnaSequence(ravel(result), Name=self.Name)

    def to_rna(self):
        """Returns a ModelDnaSequence from the data in self."""
        unpacked = self.Alphabet.unpack_arrays(self._data)
        result = zeros((len(self._data), 3))
        for i, v in enumerate(unpacked):
            result[:, i] = v
        return ModelRnaSequence(ravel(result), Name=self.Name)


class ModelDnaCodonSequence(ModelCodonSequence):
    """Holds non-degenerate DNA codon sequence."""
    Alphabet = None  # set to DNA.Alphabets.Base.Triples in moltype.py
    SequenceClass = ModelDnaSequence


class ModelRnaCodonSequence(ModelCodonSequence):
    """Holds non-degenerate DNA codon sequence."""
    Alphabet = None  # set to RNA.Alphabets.Base.Triples in motype.py
    SequenceClass = ModelRnaSequence

    def _from_string(self, s):
        """Reads from a raw string, rather than a DnaSequence."""
        s = s.upper().replace('T', 'U')  # convert to uppercase DNA
        d = self.SequenceClass(s,
                               Alphabet=self.Alphabet.SubEnumerations[0])
        self._data = d.to_codons()._data


class ModelProteinSequence(ModelSequence):
    MolType = None  # set to PROTEIN in moltype.py
    Alphabet = None  # set to PROTEIN.Alphabets.DegenGapped in moltype.py


class ModelProteinWithStopSequence(ModelSequence):
    MolType = None  # set to PROTEIN_WITH_STOP in moltype.py
    Alphabet = None  # set to PROTEIN_WITH_STOP.Alphabets.DegenGapped in moltype.py
