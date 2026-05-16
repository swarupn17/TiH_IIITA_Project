package com.gesture.app;

import android.annotation.SuppressLint;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.PermissionRequest;
import android.widget.EditText;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private ProgressBar progressBar;
    private SharedPreferences prefs;
    private EditText serverUrlInput;
    private Button connectButton;
    
    // Default URL - change this to your deployed Android/web app URL
    private static final String DEFAULT_URL = "http://10.25.205.38:3000";
    private static final String PREF_URL = "app_url";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences("GestureApp", MODE_PRIVATE);
        
        serverUrlInput = findViewById(R.id.serverUrlInput);
        connectButton = findViewById(R.id.connectButton);
        webView = findViewById(R.id.webView);
        progressBar = findViewById(R.id.progressBar);

        setupWebView();
        setupLauncherControls();
        loadSavedUrl();
    }

    private void setupLauncherControls() {
        String savedUrl = prefs.getString(PREF_URL, DEFAULT_URL);
        serverUrlInput.setText(savedUrl);

        connectButton.setOnClickListener(v -> connectToServer());
    }

    private void connectToServer() {
        String url = serverUrlInput.getText() == null ? "" : serverUrlInput.getText().toString().trim();

        if (TextUtils.isEmpty(url)) {
            Toast.makeText(this, "Enter a server URL", Toast.LENGTH_SHORT).show();
            return;
        }

        prefs.edit().putString(PREF_URL, url).apply();
        loadUrl(url);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView() {
        WebSettings webSettings = webView.getSettings();
        
        // Enable JavaScript
        webSettings.setJavaScriptEnabled(true);
        
        // Enable DOM storage
        webSettings.setDomStorageEnabled(true);
        
        // Enable media playback
        webSettings.setMediaPlaybackRequiresUserGesture(false);
        
        // Allow mixed content (HTTP on HTTPS)
        webSettings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        
        // Enable zoom
        webSettings.setBuiltInZoomControls(true);
        webSettings.setDisplayZoomControls(false);
        
        // Responsive design
        webSettings.setUseWideViewPort(true);
        webSettings.setLoadWithOverviewMode(true);

        // Handle page loading
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
            }

            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                Toast.makeText(MainActivity.this, "Error: " + description, Toast.LENGTH_SHORT).show();
            }
        });

        // Handle camera/microphone permissions
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progressBar.setProgress(newProgress);
                if (newProgress == 100) {
                    progressBar.setVisibility(View.GONE);
                } else {
                    progressBar.setVisibility(View.VISIBLE);
                }
            }

            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(() -> request.grant(request.getResources()));
            }
        });
    }

    private void loadSavedUrl() {
        String url = prefs.getString(PREF_URL, DEFAULT_URL);
        serverUrlInput.setText(url);
        loadUrl(url);
    }

    private void loadUrl(String url) {
        progressBar.setVisibility(View.VISIBLE);
        webView.loadUrl(url);
    }

    private void showUrlDialog() {
        String currentUrl = prefs.getString(PREF_URL, DEFAULT_URL);
        
        EditText input = new EditText(this);
        input.setText(currentUrl);
        input.setHint("http://your-server:port");
        input.setPadding(50, 30, 50, 30);

        new AlertDialog.Builder(this)
            .setTitle("Server URL")
            .setMessage("Enter the gesture app URL:")
            .setView(input)
            .setPositiveButton("Save", (dialog, which) -> {
                String newUrl = input.getText().toString().trim();
                if (!newUrl.isEmpty()) {
                    prefs.edit().putString(PREF_URL, newUrl).apply();
                    serverUrlInput.setText(newUrl);
                    loadUrl(newUrl);
                    Toast.makeText(this, "URL saved", Toast.LENGTH_SHORT).show();
                }
            })
            .setNegativeButton("Cancel", null)
            .setNeutralButton("Reset Default", (dialog, which) -> {
                prefs.edit().putString(PREF_URL, DEFAULT_URL).apply();
                serverUrlInput.setText(DEFAULT_URL);
                loadUrl(DEFAULT_URL);
                Toast.makeText(this, "Reset to default", Toast.LENGTH_SHORT).show();
            })
            .show();
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.main_menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        int id = item.getItemId();
        
        if (id == R.id.action_settings) {
            showUrlDialog();
            return true;
        } else if (id == R.id.action_refresh) {
            webView.reload();
            return true;
        }
        
        return super.onOptionsItemSelected(item);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
