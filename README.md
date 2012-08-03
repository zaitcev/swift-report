swift-report
============

ln -s swift-report.py swift-report

Things you need to do before this is useful:

 * Pre-position swift-report-collect.py agent at all storage nodes.
   Adjust "collect_path" in swift-report.conf accordingly.

 * Of course, ssh must accept publickey auth, too.

 * Configure the admin account in Keystone so keystone user-list works.

 * Copy /etc/swift/account.ring.gz from the proxy node (or any node).
   Copy /etc/swift/swift.conf, too. That thing is hella secret, BTW.
