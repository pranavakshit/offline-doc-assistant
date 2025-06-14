import threading
import time
from functools import wraps
from tqdm import tqdm
import sys
from contextlib import contextmanager


class DynamicProgressBar:
    def __init__(self, delay=2.0, desc="Processing", unit="it"):
        """
        Initialize dynamic progress bar
        
        Args:
            delay: Seconds to wait before showing progress bar
            desc: Description text for progress bar
            unit: Unit for progress bar
        """
        self.delay = delay
        self.desc = desc
        self.unit = unit
        self.progress_bar = None
        self.timer = None
        self.should_show = False
        self.lock = threading.Lock()
        
    def _show_progress(self):
        """Show indeterminate progress bar after delay"""
        with self.lock:
            if self.should_show:
                self.progress_bar = tqdm(
                    desc=self.desc,
                    unit=self.unit,
                    ncols=80,
                    bar_format='{desc}: {elapsed} | {rate_fmt}',
                    leave=False
                )
                # Keep updating the progress bar
                while self.should_show:
                    if self.progress_bar:
                        self.progress_bar.update(1)
                    time.sleep(0.1)
    
    def start(self):
        """Start the delayed progress bar"""
        self.should_show = True
        self.timer = threading.Timer(self.delay, self._show_progress)
        self.timer.start()
    
    def stop(self):
        """Stop and clean up the progress bar"""
        self.should_show = False
        if self.timer:
            self.timer.cancel()
        with self.lock:
            if self.progress_bar:
                self.progress_bar.close()
                self.progress_bar = None


@contextmanager  
def dynamic_progress(desc="Processing", delay=2.0, unit="it"):
    """Context manager for dynamic progress bars"""
    progress = DynamicProgressBar(delay=delay, desc=desc, unit=unit)
    progress.start()
    try:
        yield progress
    finally:
        progress.stop()


def with_progress(desc="Processing", delay=2.0, unit="it"):
    """Decorator for adding dynamic progress bars to functions"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with dynamic_progress(desc=desc, delay=delay, unit=unit):
                return func(*args, **kwargs)
        return wrapper
    return decorator


class ProgressBarManager:
    """Centralized progress bar management for different operations"""
    
    @staticmethod
    def document_loading_progress(total_docs=None):
        """Progress bar for document loading"""
        if total_docs:
            return tqdm(
                total=total_docs,
                desc="📚 Loading documents",
                unit="doc",
                ncols=80,
                bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )
        else:
            return tqdm(
                desc="📚 Loading documents",
                unit="doc", 
                ncols=80,
                bar_format='{desc}: {n_fmt} docs [{elapsed}]'
            )
    
    @staticmethod  
    def embedding_progress(total_lines=None):
        """Progress bar for embedding generation"""
        if total_lines:
            return tqdm(
                total=total_lines,
                desc="🧠 Generating embeddings",
                unit="line",
                ncols=80,
                bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )
        else:
            return tqdm(
                desc="🧠 Generating embeddings",
                unit="line",
                ncols=80,
                bar_format='{desc}: {n_fmt} lines [{elapsed}]'
            )
    
    @staticmethod
    def search_progress():
        """Progress bar for search operations"""
        return tqdm(
            desc="🔍 Searching documents",
            unit="doc",
            ncols=80,
            bar_format='{desc}: {elapsed}',
            leave=False
        )


# Specific progress contexts for your application
def loading_progress():
    """Progress context for initial loading"""
    return dynamic_progress(desc="🚀 Initializing AI models", delay=1.5)


def rephrasing_progress():
    """Progress context for rephrasing operations"""
    return dynamic_progress(desc="✏️ Rephrasing text", delay=1.0)


def summarizing_progress():
    """Progress context for summarization"""
    return dynamic_progress(desc="📋 Generating summary", delay=1.5)


def ocr_progress():
    """Progress context for OCR operations"""  
    return dynamic_progress(desc="👁️ Processing with OCR", delay=2.0)


def search_progress():
    """Progress context for search operations"""
    return dynamic_progress(desc="🔍 Searching documents", delay=0.5)