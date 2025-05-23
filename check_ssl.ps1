# Проверка SSL сертификата
$Domain = "your-domain.com"
$Port = "443"
$SSLCertificate = $null

try {
    Write-Host "Checking SSL certificate for $Domain..."
    $TCPClient = New-Object -TypeName System.Net.Sockets.TcpClient
    $TCPClient.Connect($Domain, $Port)
    
    $SSLStream = New-Object -TypeName System.Net.Security.SslStream -ArgumentList @($TCPClient.GetStream(), $true, {
        param($sender, $certificate, $chain, $errors)
        return $true
    })
    
    $SSLStream.AuthenticateAsClient($Domain)
    $SSLCertificate = $SSLStream.RemoteCertificate
    
    Write-Host "SSL Certificate Details:"
    Write-Host "Subject: $($SSLCertificate.Subject)"
    Write-Host "Issuer: $($SSLCertificate.Issuer)"
    Write-Host "Valid From: $($SSLCertificate.GetEffectiveDateString())"
    Write-Host "Valid To: $($SSLCertificate.GetExpirationDateString())"
    
    $DaysUntilExpiration = ([DateTime]$SSLCertificate.GetExpirationDateString() - (Get-Date)).Days
    Write-Host "Days until expiration: $DaysUntilExpiration"
    
    if ($DaysUntilExpiration -lt 30) {
        Write-Host "WARNING: Certificate will expire in less than 30 days!" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "Error checking SSL certificate: $_" -ForegroundColor Red
}
finally {
    if ($null -ne $TCPClient) {
        $TCPClient.Dispose()
    }
    if ($null -ne $SSLStream) {
        $SSLStream.Dispose()
    }
}
