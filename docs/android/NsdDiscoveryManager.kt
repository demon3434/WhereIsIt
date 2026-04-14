@file:Suppress("DEPRECATION")

package com.whereisit.discovery

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Handler
import android.os.Looper
import java.util.Locale


data class WhereIsItEndpoint(
    val host: String,
    val port: Int,
    val source: String,
    val serviceName: String
)

class NsdDiscoveryManager(
    context: Context,
    private val rawServiceType: String = "_whereisit._tcp",
    private val discoveryTimeoutMs: Long = 10_000L,
    private val maxAttempts: Int = 3
) {
    private val appContext = context.applicationContext
    private val nsdManager = appContext.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val wifiManager = appContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
    private val mainHandler = Handler(Looper.getMainLooper())

    private var currentListener: NsdManager.DiscoveryListener? = null
    private var timeoutRunnable: Runnable? = null
    private var multicastLock: WifiManager.MulticastLock? = null
    private var attempts = 0
    private var stopped = false
    private var found = false
    private val deliveredKeys = linkedSetOf<String>()

    fun start(onFound: (WhereIsItEndpoint) -> Unit, onFailed: (String) -> Unit) {
        stop()
        stopped = false
        found = false
        attempts = 0
        deliveredKeys.clear()
        startAttempt(onFound, onFailed)
    }

    fun stop() {
        stopped = true
        clearTimeout()
        stopCurrentDiscovery()
        releaseMulticastLock()
        mainHandler.removeCallbacksAndMessages(null)
    }

    private fun startAttempt(onFound: (WhereIsItEndpoint) -> Unit, onFailed: (String) -> Unit) {
        if (stopped || found) return
        attempts += 1
        val type = normalizeServiceType(rawServiceType)
        acquireMulticastLock()

        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {
                timeoutRunnable = Runnable {
                    if (stopped || found) return@Runnable
                    stopCurrentDiscovery()
                    if (attempts < maxAttempts) {
                        startAttempt(onFound, onFailed)
                    } else {
                        onFailed("NSD timeout after $maxAttempts attempts, type=$type")
                    }
                }
                mainHandler.postDelayed(timeoutRunnable!!, discoveryTimeoutMs)
            }

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                resolveService(serviceInfo, onFound)
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) = Unit

            override fun onDiscoveryStopped(serviceType: String) = Unit

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                clearTimeout()
                stopCurrentDiscovery()
                if (stopped || found) return
                if (attempts < maxAttempts) {
                    startAttempt(onFound, onFailed)
                } else {
                    onFailed("NSD start failed($errorCode), type=$serviceType")
                }
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                clearTimeout()
                stopCurrentDiscovery()
            }
        }

        currentListener = listener
        nsdManager.discoverServices(type, NsdManager.PROTOCOL_DNS_SD, listener)
    }

    private fun resolveService(serviceInfo: NsdServiceInfo, onFound: (WhereIsItEndpoint) -> Unit) {
        nsdManager.resolveService(serviceInfo, object : NsdManager.ResolveListener {
            override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) = Unit

            override fun onServiceResolved(resolved: NsdServiceInfo) {
                if (stopped || found) return

                // Prefer SRV(host/port), fallback to TXT(host/mappedPort).
                val srvHost = resolved.host?.hostAddress?.orEmpty()
                val srvPort = resolved.port
                val attrs = resolved.attributes.mapValues { (_, v) ->
                    runCatching { String(v, Charsets.UTF_8) }.getOrDefault("")
                }

                val txtHost = attrs["host"].orEmpty()
                val txtPort = attrs["mappedPort"]?.toIntOrNull() ?: 0

                val host = when {
                    srvHost.isNotBlank() -> srvHost
                    txtHost.isNotBlank() -> txtHost
                    else -> ""
                }
                val port = when {
                    srvPort > 0 -> srvPort
                    txtPort > 0 -> txtPort
                    else -> 0
                }
                if (host.isBlank() || port <= 0) return

                val key = "$host:$port"
                if (!deliveredKeys.add(key)) return

                found = true
                clearTimeout()
                stopCurrentDiscovery()
                releaseMulticastLock()

                onFound(
                    WhereIsItEndpoint(
                        host = host,
                        port = port,
                        source = if (srvHost.isNotBlank() && srvPort > 0) "SRV" else "TXT",
                        serviceName = resolved.serviceName
                    )
                )
            }
        })
    }

    private fun stopCurrentDiscovery() {
        currentListener?.let {
            runCatching { nsdManager.stopServiceDiscovery(it) }
        }
        currentListener = null
    }

    private fun clearTimeout() {
        timeoutRunnable?.let { mainHandler.removeCallbacks(it) }
        timeoutRunnable = null
    }

    @SuppressLint("MissingPermission")
    private fun acquireMulticastLock() {
        if (multicastLock?.isHeld == true) return
        multicastLock = wifiManager.createMulticastLock("whereisit-mdns").apply {
            setReferenceCounted(true)
            acquire()
        }
    }

    private fun releaseMulticastLock() {
        multicastLock?.let {
            if (it.isHeld) {
                runCatching { it.release() }
            }
        }
        multicastLock = null
    }

    companion object {
        fun normalizeServiceType(input: String): String {
            // NsdManager prefers `_service._tcp` format.
            var s = input.trim().lowercase(Locale.US)
            if (s.isBlank()) return "_whereisit._tcp"
            s = s.removeSuffix(".")
            if (s.endsWith(".local")) s = s.removeSuffix(".local")
            s = s.removeSuffix(".")
            return if (s.endsWith("._tcp") || s.endsWith("._udp")) s else "_whereisit._tcp"
        }

        val REQUIRED_PERMISSIONS = listOf(
            Manifest.permission.INTERNET,
            Manifest.permission.ACCESS_NETWORK_STATE,
            Manifest.permission.ACCESS_WIFI_STATE,
            Manifest.permission.CHANGE_WIFI_MULTICAST_STATE
        )
    }
}
