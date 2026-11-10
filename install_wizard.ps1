Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }

$defaultDest = Join-Path ([System.Environment]::GetFolderPath('LocalApplicationData')) "Programs\PHARMAKON 3.2"

# Main Form
$form = New-Object System.Windows.Forms.Form
$form.Text = "PHARMAKON 3.2 (v3.2.0) // Installation Wizard"
$form.Size = New-Object System.Drawing.Size(560, 420)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(13, 17, 23)
$form.ForeColor = [System.Drawing.Color]::FromArgb(240, 246, 252)

# Icon
$icoPath = Join-Path $scriptDir "pharmakon_hd_256.ico"
if (-not (Test-Path $icoPath)) { $icoPath = Join-Path $scriptDir "_internal\pharmakon_hd_256.ico" }
if (Test-Path $icoPath) {
    try { $form.Icon = New-Object System.Drawing.Icon($icoPath) } catch {}
}

# Header Label
$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "PHARMAKON 3.2 Studio Console"
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = [System.Drawing.Color]::FromArgb(6, 182, 212)
$lblTitle.Location = New-Object System.Drawing.Point(24, 18)
$lblTitle.Size = New-Object System.Drawing.Size(500, 32)
$form.Controls.Add($lblTitle)

$lblSub = New-Object System.Windows.Forms.Label
$lblSub.Text = "Neural Audio Antidote & Stem Mastering Setup | Build v3.2.0"
$lblSub.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$lblSub.ForeColor = [System.Drawing.Color]::FromArgb(148, 163, 184)
$lblSub.Location = New-Object System.Drawing.Point(26, 52)
$lblSub.Size = New-Object System.Drawing.Size(500, 20)
$form.Controls.Add($lblSub)

# Separator Line
$sep = New-Object System.Windows.Forms.Label
$sep.BorderStyle = "Fixed3D"
$sep.Location = New-Object System.Drawing.Point(24, 80)
$sep.Size = New-Object System.Drawing.Size(496, 2)
$form.Controls.Add($sep)

# Destination Group
$lblDest = New-Object System.Windows.Forms.Label
$lblDest.Text = "Destination Directory (where to install):"
$lblDest.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
$lblDest.Location = New-Object System.Drawing.Point(24, 98)
$lblDest.Size = New-Object System.Drawing.Size(350, 20)
$form.Controls.Add($lblDest)

$txtDest = New-Object System.Windows.Forms.TextBox
$txtDest.Text = $defaultDest
$txtDest.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)
$txtDest.Location = New-Object System.Drawing.Point(26, 122)
$txtDest.Size = New-Object System.Drawing.Size(388, 25)
$txtDest.BackColor = [System.Drawing.Color]::FromArgb(22, 27, 34)
$txtDest.ForeColor = [System.Drawing.Color]::FromArgb(240, 246, 252)
$form.Controls.Add($txtDest)

$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Text = "Browse..."
$btnBrowse.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnBrowse.Location = New-Object System.Drawing.Point(422, 120)
$btnBrowse.Size = New-Object System.Drawing.Size(98, 28)
$btnBrowse.BackColor = [System.Drawing.Color]::FromArgb(33, 38, 45)
$btnBrowse.ForeColor = [System.Drawing.Color]::White
$btnBrowse.FlatStyle = "Flat"
$btnBrowse.Add_Click({
    $fbd = New-Object System.Windows.Forms.FolderBrowserDialog
    $fbd.Description = "Select destination folder for PHARMAKON 3.2"
    $fbd.SelectedPath = $txtDest.Text
    if ($fbd.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $txtDest.Text = $fbd.SelectedPath
    }
})
$form.Controls.Add($btnBrowse)

# Options Checkboxes
$chkDesktop = New-Object System.Windows.Forms.CheckBox
$chkDesktop.Text = "Create Desktop Shortcut (with gold studio icon)"
$chkDesktop.Checked = $true
$chkDesktop.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)
$chkDesktop.Location = New-Object System.Drawing.Point(28, 168)
$chkDesktop.Size = New-Object System.Drawing.Size(450, 24)
$form.Controls.Add($chkDesktop)

$chkStartMenu = New-Object System.Windows.Forms.CheckBox
$chkStartMenu.Text = "Create Start Menu Shortcut"
$chkStartMenu.Checked = $true
$chkStartMenu.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)
$chkStartMenu.Location = New-Object System.Drawing.Point(28, 196)
$chkStartMenu.Size = New-Object System.Drawing.Size(450, 24)
$form.Controls.Add($chkStartMenu)

$chkLaunch = New-Object System.Windows.Forms.CheckBox
$chkLaunch.Text = "Launch PHARMAKON 3.2 immediately after installation"
$chkLaunch.Checked = $true
$chkLaunch.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)
$chkLaunch.Location = New-Object System.Drawing.Point(28, 224)
$chkLaunch.Size = New-Object System.Drawing.Size(450, 24)
$form.Controls.Add($chkLaunch)

# Status Label & Progress Bar
$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "Ready to install."
$lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(100, 116, 139)
$lblStatus.Location = New-Object System.Drawing.Point(26, 266)
$lblStatus.Size = New-Object System.Drawing.Size(490, 20)
$form.Controls.Add($lblStatus)

$pBar = New-Object System.Windows.Forms.ProgressBar
$pBar.Location = New-Object System.Drawing.Point(26, 290)
$pBar.Size = New-Object System.Drawing.Size(494, 16)
$pBar.Style = "Continuous"
$form.Controls.Add($pBar)

# Install Action Button
$btnInstall = New-Object System.Windows.Forms.Button
$btnInstall.Text = "INSTALL PHARMAKON"
$btnInstall.Font = New-Object System.Drawing.Font("Segoe UI", 10.5, [System.Drawing.FontStyle]::Bold)
$btnInstall.Location = New-Object System.Drawing.Point(280, 324)
$btnInstall.Size = New-Object System.Drawing.Size(240, 40)
$btnInstall.BackColor = [System.Drawing.Color]::FromArgb(16, 185, 129)
$btnInstall.ForeColor = [System.Drawing.Color]::Black
$btnInstall.FlatStyle = "Flat"
$btnInstall.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnCancel = New-Object System.Windows.Forms.Button
$btnCancel.Text = "Cancel"
$btnCancel.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)
$btnCancel.Location = New-Object System.Drawing.Point(170, 324)
$btnCancel.Size = New-Object System.Drawing.Size(98, 40)
$btnCancel.BackColor = [System.Drawing.Color]::FromArgb(33, 38, 45)
$btnCancel.ForeColor = [System.Drawing.Color]::White
$btnCancel.FlatStyle = "Flat"
$btnCancel.Add_Click({ $form.Close() })
$form.Controls.Add($btnCancel)

$btnInstall.Add_Click({
    $targetDir = $txtDest.Text.Trim()
    if (-not $targetDir) {
        [System.Windows.Forms.MessageBox]::Show("Please specify a destination folder.", "Installation Error", "OK", "Warning")
        return
    }

    $btnInstall.Enabled = $false
    $btnCancel.Enabled = $false
    $btnBrowse.Enabled = $false
    $txtDest.Enabled = $false
    $pBar.Value = 20
    $lblStatus.Text = "Preparing installation directory..."
    $form.Refresh()

    try {
        if (-not (Test-Path $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        }

        # Check if installing in-place
        $srcFull = [System.IO.Path]::GetFullPath($scriptDir).TrimEnd('\')
        $dstFull = [System.IO.Path]::GetFullPath($targetDir).TrimEnd('\')

        if ($srcFull -ne $dstFull) {
            $lblStatus.Text = "Copying PHARMAKON 3.2 files..."
            $pBar.Value = 40
            $form.Refresh()

            # Copy all files except self if running inside
            Get-ChildItem -Path $scriptDir | ForEach-Object {
                Copy-Item -Path $_.FullName -Destination $targetDir -Recurse -Force
            }
        }

        $pBar.Value = 70
        $lblStatus.Text = "Configuring shortcuts and icons..."
        $form.Refresh()

        $wsh = New-Object -ComObject WScript.Shell
        $targetExe = Join-Path $targetDir "Start_Pharmakon.bat"
        if (-not (Test-Path $targetExe)) {
            $targetExe = Join-Path $targetDir "Pharmakon.exe"
        }

        $iconTarget = Join-Path $targetDir "pharmakon_hd_256.ico"
        if (-not (Test-Path $iconTarget)) {
            $iconTarget = Join-Path $targetDir "_internal\pharmakon_hd_256.ico"
        }

        # 1. Desktop Shortcut
        if ($chkDesktop.Checked) {
            $desktopDir = [System.Environment]::GetFolderPath('Desktop')
            $deskShortcut = $wsh.CreateShortcut((Join-Path $desktopDir "PHARMAKON 3.2.lnk"))
            $deskShortcut.TargetPath = $targetExe
            $deskShortcut.WorkingDirectory = $targetDir
            $deskShortcut.Description = "PHARMAKON 3.2 Studio Console // Neural Audio Antidote & Stem Mastering"
            if (Test-Path $iconTarget) {
                $deskShortcut.IconLocation = "$iconTarget,0"
            }
            $deskShortcut.Save()
        }

        # 2. Start Menu Shortcut
        if ($chkStartMenu.Checked) {
            $programsDir = Join-Path ([System.Environment]::GetFolderPath('Programs')) "PHARMAKON 3.2"
            if (-not (Test-Path $programsDir)) {
                New-Item -ItemType Directory -Path $programsDir -Force | Out-Null
            }
            $startShortcut = $wsh.CreateShortcut((Join-Path $programsDir "PHARMAKON 3.2.lnk"))
            $startShortcut.TargetPath = $targetExe
            $startShortcut.WorkingDirectory = $targetDir
            $startShortcut.Description = "PHARMAKON 3.2 Studio Console"
            if (Test-Path $iconTarget) {
                $startShortcut.IconLocation = "$iconTarget,0"
            }
            $startShortcut.Save()
        }

        $pBar.Value = 100
        $lblStatus.Text = "Installation completed successfully!"
        $form.Refresh()

        # 3. Launch if requested
        if ($chkLaunch.Checked) {
            Start-Process -FilePath $targetExe -WorkingDirectory $targetDir
        }

        [System.Windows.Forms.MessageBox]::Show(
            "PHARMAKON v3.2.0 has been installed successfully!`n`nLocation: $targetDir`nDesktop Shortcut: Created",
            "Installation Complete",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        )

        $form.Close()
    }
    catch {
        [System.Windows.Forms.MessageBox]::Show("Error during installation:`n$_", "Installation Error", "OK", "Error")
        $btnInstall.Enabled = $true
        $btnCancel.Enabled = $true
    }
})

$form.Controls.Add($btnInstall)

[void]$form.ShowDialog()
