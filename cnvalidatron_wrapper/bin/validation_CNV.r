# Script to run validation of the CNV data

# Start time
    start_time <- Sys.time()

# Libraries
    suppressPackageStartupMessages({
        library(BiocManager)
        library(data.table)
        library(BiocParallel)
        library(torch)
        library(stringr)
        library(luz)
        library(CNValidatron)
        library(parallel)
        library(argparse)
    })

# Custom function to fix error
    # Slightly different from the original CNValidatron function to accommodate the new data structure (absence of conf and length columns in the CNVs data.table)
    make_predictions <- function(model, root, cnvs, return_pred_dt = F, batches = 1:1000){
        pred_dt_rbind <- data.table()
        for (i in batches) {
            #message(i)
            bpt <- paste0(root, "/batch", i, "/")
            if (!dir.exists(bpt)) 
                next
            pred_dt <- image_folder_dataset(bpt, transform = . %>% transform_to_tensor())
            pred_tens <- predict(model, pred_dt)
            # check if there's only a single picture in the folder --> then the pred_tens is a single tensor and will fail otherwise
            if (pred_tens$ndim == 1) {
                pred_tens <- pred_tens$unsqueeze(1)  # Convert shape [C] -> [1, C]
            }
            pred_tens <- nnf_softmax(pred_tens, dim = 2)
            pred_ix <- as.matrix(torch_argmax(pred_tens, dim = 2))[, 1]
            pred_probs <- round(as.matrix(pred_tens), 3)
            pred_dt <- data.table(ix = pred_dt$samples[[1]], pred = pred_ix)
            for (i in 1:nrow(pred_dt)) pred_dt[i, `:=`(pred_prob, 
                pred_probs[i, pred_ix[i]])]
            pred_probs <- as.data.table(pred_probs)
            colnames(pred_probs) <- c("p_false", "p_true_del", "p_true_dup")
            pred_dt <- cbind(pred_dt, pred_probs)
            pred_dt[, `:=`(sample_ID, gsub(".+samp", "", ix))][, 
                `:=`(sample_ID, as.character(gsub("_.+", "", sample_ID)))][, 
                `:=`(start, gsub(".+st", "", ix))][, `:=`(start, 
                as.integer(gsub("_.+", "", start)))][, `:=`(real_numsnp, 
                gsub(".+nsnp", "", ix))][, `:=`(real_numsnp, as.integer(gsub("\\.png", 
                "", real_numsnp)))]
            pred_dt_rbind <- rbind(pred_dt_rbind, pred_dt)
        }
        if (return_pred_dt){
            return(pred_dt_rbind)
        } else {
            pred_dt_rbind[, `:=`(ix, NULL)]
            cnvs[, `:=`(sample_ID = as.character(sample_ID), start = as.integer(start))]
            # error as the conf column is not present in the cnvs data.table --> add a tryCatch statement
            #pred_dt <- merge(pred_dt_rbind, cnvs[, .(sample_ID, chr, start, end, numsnp, length, conf, GT, CN)], by = c("sample_ID", "start"))
            pred_dt <- merge(pred_dt_rbind, cnvs[, .(sample_ID, chr, start, end, numsnp, GT, CN)], by = c("sample_ID", "start"))
            return(pred_dt)
        }
    }

# Argument parser
    parser <- ArgumentParser(description = "Run CNV validation")
    parser$add_argument("--batch", type = "integer", required = TRUE, help = "Batch number to process when running in parallel")
    parser$add_argument("--snps", type = "character", required = TRUE, help = "Path to SNPs input file")
    parser$add_argument("--cnvs", type = "character", required = TRUE, help = "Path to CNVs input file")
    parser$add_argument("--samples", type = "character", required = TRUE, help = "Path to samples input file")
    parser$add_argument("--model", type = "character", required = TRUE, help = "Path to trained model file")
    parser$add_argument("--outdir", type = "character", required = TRUE, help = "Output directory for results")
    args <- parser$parse_args()

# Put arguments into variables
    batch <- args$batch
    snps_path <- args$snps
    cnvs_path <- args$cnvs
    samples_path <- args$samples
    model_path <- args$model
    outdir <- args$outdir

# Load necessary objects
    snps <- fread(snps_path)
    # Preserve explicit manifest IDs, including numeric-looking IDs with leading zeros.
    cnvs <- fread(cnvs_path, colClasses = list(character = "sample_ID"))
    samples <- fread(samples_path, colClasses = list(character = "sample_ID"))

# Make sure all data is a data tables
    snps <- as.data.table(snps)
    cnvs <- as.data.table(cnvs)
    samples <- as.data.table(samples)

# Trial run, restricted to 10 samples
    # Then subset cnv and sample files
    cnvs_sb = cnvs[cnvs$sample_ID %in% samples$sample_ID, ]

# Select the folder for PNG files
    png_pt <- paste0(outdir, '/pngs')

# Set BiocParall parallel worker limit -- parallelization has issues -- disable for now
    #BiocParallel::register(BiocParallel::MulticoreParam(workers=4, progressbar = TRUE))

# Save the PNGs for all CNVs
    save_pngs_prediction(root = png_pt, cnvs = cnvs_sb, samps = samples, snps = snps, no_parall = T)
    
# run the prediction algoritm
    preds <- make_predictions(luz::luz_load(model_path), png_pt, cnvs)

# Write output
    out_path <- paste0(outdir, '/predictions.txt')
    write.table(preds, out_path, row.names = FALSE, col.names = TRUE, quote = FALSE, sep = "\t")

# select predicted true CNVs with probability above 0.5
    true_cnvs <- preds[preds$pred_prob >= 0.5, ]

# End time
    end_time <- Sys.time()
    print(paste("Time taken for predictions:", end_time - start_time, '~ this for', length(unique(preds$sample_ID)), 'samples and', nrow(preds), 'CNVs'))

# the model has three categories
# 1: False
# 2: True Deletion
# 3: True Duplication

# Benchmarking speed without parallelization
#    start_time <- Sys.time()
#    save_pngs_prediction(root = png_pt, cnvs = cnvs_sb, samps = samples_sb, snps = snps, no_parall = T)
#    preds <- make_predictions(luz::luz_load(model_path), root = png_pt, cnvs = cnvs_sb, return_pred_dt = T, batches = 1:1000)
#    end_time <- Sys.time()
#    print(paste("Time taken for predictions without parallelization:", end_time - start_time, '~ this for', length(unique(preds$sample_ID)), 'samples and', nrow(preds), 'CNVs'))
    # 13.82 seconds ~ this for 1 samples and 19 CNVs
    # 1.47 minutes ~ this for 5 samples and 144 CNVs
    # 2.4 minutes ~ this for 10 samples and 235 CNVs
    # Estimated time for 1000 samples and 10000 CNVs: ~ 4.5 hours
