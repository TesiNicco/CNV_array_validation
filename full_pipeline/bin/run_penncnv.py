"""PennCNV calling and filtering with configurable paths and thresholds."""
from pathlib import Path

from common import run


def call_batch(cfg, batch, prepared, root):
    tool = Path(cfg['tools']['penncnv_dir'])
    log = root / 'penncnv.commands.log'
    out = root / 'penncnv'
    out.mkdir()
    samplelist = out / 'samples.txt'
    samplelist.write_text(''.join(s['signal_file'] + '\n' for s in prepared))
    pfb = out / 'probes.pfb'

    def penn(name, *args, stdout=None):
        run(['perl', tool / name, *args], log, stdout=stdout)

    penn('compile_pfb.pl', '--output', pfb, '--listfile', samplelist)
    if cfg['adjust_lrr']:
        gcmodel = out / 'gcmodel.txt'
        penn('cal_gc_snp.pl', cfg['references']['gc_file'], pfb, '-output', gcmodel)
        penn('genomic_wave.pl', '-adjust', '-gcmodel', gcmodel, '-list', samplelist)
        for sample in prepared:
            sample['signal_file'] += '.adjusted'
            if not Path(sample['signal_file']).is_file():
                raise FileNotFoundError(sample['signal_file'])
        samplelist = out / 'samples_adjusted.txt'
        samplelist.write_text(''.join(s['signal_file'] + '\n' for s in prepared))
    raw = out / 'step0.rawcnv'
    qclog = out / 'step0.log'
    penn('detect_cnv.pl', '-test', '-hmm', tool / 'lib/hhall.hmm', '-pfb', pfb,
         '--list', samplelist, '-log', qclog, '-out', raw)
    qc = cfg['qc']
    filtered = out / 'step1.goodcnv'
    penn('filter_cnv.pl', raw, '--qclogfile', qclog,
         '-qclrrsd', qc['lrr_sd'], '-qcbafdrift', qc['baf_drift'],
         '-qcwf', qc['wave_factor'], '-qcpassout', out / 'step1.qcpass',
         '-qcsumout', out / 'step1.qcsum', '-numsnp', qc['min_snps'],
         '-length', qc['min_length_bp'], '-out', filtered)
    merged = out / 'step2_merged.goodcnv'
    # Preserve empty-CNV batches without calling tools on an empty file.
    if not filtered.read_text().strip():
        merged.write_text('')
    else:
        penn('clean_cnv.pl', 'combineseg', '--fraction', qc['merge_fraction'],
             '--bp', '--signalfile', pfb, filtered, stdout=merged)
    flagged = out / 'excluded_region_hits.txt'
    if merged.read_text().strip():
        penn('scan_region.pl', merged, cfg['references']['excluded_regions'],
             '-minqueryfrac', qc['excluded_region_overlap'], stdout=flagged)
    else:
        flagged.write_text('')
    # Reproduce fgrep -v -f with explicit handling of an empty exclusion list.
    patterns = flagged.read_text().splitlines()
    if any(not pattern for pattern in patterns):
        raise ValueError('Blank exclusion pattern from scan_region.pl; inspect its output')
    final = out / 'step3.goodcnv.excludeBadRegions'
    with merged.open() as source, final.open('w') as target:
        for line in source:
            if not any(pattern in line for pattern in patterns):
                target.write(line)
    return pfb, final, prepared
