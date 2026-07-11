/* ═══════════════════════════════════════════════════════════
   MEDICATE INTERACTIVE ANIMATIONS — JAVASCRIPT
   ═══════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
  // ── 1. Loading Splash Screen ──────────────────────────────
  const splash = document.getElementById('loading-splash');
  const progressBar = document.querySelector('.splash-progress-fill');
  const splashTexts = [
    "Initializing disease prediction models...",
    "Connecting to secure doctor network...",
    "Securing medical gateway...",
    "Ready!"
  ];
  const splashTextElement = document.querySelector('.splash-text');

  if (splash) {
    // Check if user already saw splash in this session
    const hasSeenSplash = sessionStorage.getItem('hasSeenSplash');
    
    if (hasSeenSplash) {
      splash.style.display = 'none';
    } else {
      let progress = 0;
      let textIndex = 0;
      
      const progressInterval = setInterval(() => {
        progress += Math.floor(Math.random() * 15) + 5;
        if (progress >= 100) {
          progress = 100;
          clearInterval(progressInterval);
          
          if (splashTextElement) splashTextElement.textContent = splashTexts[3];
          
          setTimeout(() => {
            splash.style.opacity = '0';
            splash.style.visibility = 'hidden';
            sessionStorage.setItem('hasSeenSplash', 'true');
          }, 400);
        } else {
          // Update text description as progress increments
          const targetTextIndex = Math.min(Math.floor(progress / 30), splashTexts.length - 2);
          if (splashTextElement && targetTextIndex !== textIndex) {
            textIndex = targetTextIndex;
            splashTextElement.textContent = splashTexts[textIndex];
          }
        }
        
        if (progressBar) {
          progressBar.style.width = progress + '%';
        }
      }, 100);
    }
  }

  // ── 2. Navbar Scroll Behavior ─────────────────────────────
  const header = document.querySelector('.main-header');
  if (header) {
    const checkScroll = () => {
      if (window.scrollY > 20) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }
    };
    window.addEventListener('scroll', checkScroll);
    checkScroll(); // Run once at load
  }

  // ── 3. Scroll Triggered Fade-Up Elements ──────────────────
  const fadeUpElements = document.querySelectorAll('.fade-up-trigger');
  if (fadeUpElements.length > 0) {
    const observerOptions = {
      root: null,
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target); // Trigger once
        }
      });
    }, observerOptions);
    
    fadeUpElements.forEach(el => observer.observe(el));
  }

  // ── 4. Toast Alerts Auto-Dismiss ──────────────────────────
  const alerts = document.querySelectorAll('.alert-nb');
  alerts.forEach(alert => {
    // Set auto-dismiss timeout
    const timeout = setTimeout(() => {
      dismissAlert(alert);
    }, 5000);
    
    // Close button click listener
    const closeBtn = alert.querySelector('.alert-nb-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        clearTimeout(timeout);
        dismissAlert(alert);
      });
    }
  });

  function dismissAlert(alertEl) {
    alertEl.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
    alertEl.style.transform = 'translateX(120%)';
    alertEl.style.opacity = '0';
    setTimeout(() => {
      alertEl.remove();
    }, 300);
  }

  // ── 5. Mobile Navbar Drawer ───────────────────────────────
  const menuBtn = document.querySelector('.menu-toggle');
  const navLinks = document.querySelector('.nav-links');
  
  if (menuBtn && navLinks) {
    menuBtn.addEventListener('click', () => {
      // Simple toggle for mobile viewports
      navLinks.classList.toggle('active');
      const isActive = navLinks.classList.contains('active');
      
      // Update hamburger icon states if desired
      if (isActive) {
        menuBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide h-5 w-5 stroke-[2.5]"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;
      } else {
        menuBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide h-5 w-5 stroke-[2.5]"><line x1="4" y1="12" x2="20" y2="12"></line><line x1="4" y1="6" x2="20" y2="6"></line><line x1="4" y1="19" x2="20" y2="19"></line></svg>`;
      }
    });
  }
});
