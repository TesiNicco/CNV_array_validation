# Install runtime files in a dedicated R process. A fresh process verifies loading.
options(timeout = 1200)
prefix <- Sys.getenv("CONDA_PREFIX")
if (!nzchar(prefix)) stop("Run this script through setup_environment.sh")
prefix <- normalizePath(prefix, mustWork = TRUE)
target_library <- normalizePath(file.path(R.home(), "library"), mustWork = TRUE)
if (!startsWith(target_library, paste0(prefix, "/"))) stop("Rscript is outside the mamba environment")
if (file.access(target_library, 2) != 0) stop("R library is not writable: ", target_library)
.libPaths(target_library, include.site = FALSE)

# Here torch_is_installed checks file presence only. Its load verification caches
# state in the Torch namespace and can fail after installation in the same R
# session. setup_environment.sh enables load verification in the NEXT process.
Sys.setenv(TORCH_INSTALL = "0", TORCH_LOAD = "0", TORCH_VERIFY_LOAD = "FALSE",
           CUDA = "cpu", TORCH_HOME = file.path(target_library, "torch"))
if (!requireNamespace("torch", quietly = TRUE)) stop("Missing conda dependency: torch")
if (!torch::torch_is_installed()) {
    message("Installing Torch CPU runtime")
    torch::install_torch()
}
if (!torch::torch_is_installed()) stop("Torch runtime files are missing after installation")
message("Torch runtime files are present; loading will be checked in a fresh R process")
